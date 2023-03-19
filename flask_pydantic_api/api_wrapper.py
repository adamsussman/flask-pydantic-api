import asyncio
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from asgiref.sync import async_to_sync
from flask import current_app, jsonify, make_response, request
from pydantic import BaseModel, ValidationError
from pydantic.tools import parse_obj_as

from .utils import get_annotated_models

augment_schema_with_fieldsets: Optional[Callable] = None
render_fieldset_model: Optional[Callable] = None

try:
    from pydantic_enhanced_serializer import (
        augment_schema_with_fieldsets,
        render_fieldset_model,
    )
except ImportError:
    pass


def get_request_args(
    view_kwargs: Dict[str, Any],
    for_model: Optional[Type[BaseModel]] = None,
    merge_path_parameters: Optional[bool] = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    args: Dict[str, Any] = {}

    if request.is_json and request.json:
        args.update(request.json)
    elif request.query_string:
        args.update(request.args.to_dict())
        if for_model:
            args.update(
                {
                    k: v
                    for k, v in request.args.to_dict(flat=False).items()
                    if k in for_model.__fields__
                    and for_model.__fields__[k].is_complex()
                }
            )

    # Merge path arguments into request data, if wanted
    if (
        merge_path_parameters
        and view_kwargs
        and request.url_rule
        and request.url_rule.arguments
    ):
        args.update(
            {k: v for k, v in view_kwargs.items() if k in request.url_rule.arguments}
        )
        for argument_name in request.url_rule.arguments:
            view_kwargs.pop(argument_name, None)

    return args, view_kwargs


# pydantic_enhanced_serializer: Add extra schema information for the openapi
def augment_pydantic_enhanced_serializer_model_schemas(
    *models: Optional[Type[BaseModel]],
) -> None:
    if not augment_schema_with_fieldsets:
        return

    for model in models:
        if model:
            augment_schema_with_fieldsets(model)


# decorator that can be composed with regular Flask @blueprint.get/post/etc decorators.
# This decorator uses type signatures to figure out the request and response pydantic models.
def pydantic_api(
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    success_status_code: int = 200,
    maximum_expansion_depth=5,
    request_fields_name: str = "fields",
    merge_path_parameters: bool = False,
) -> Callable:
    def wrap(view_func: Callable) -> Callable:
        request_model_param_name, request_model, response_models = get_annotated_models(
            view_func
        )

        @wraps(view_func)
        def wrapped_endpoint(*args: Any, **kwargs: Any) -> Callable:
            body, kwargs = (
                get_request_args(
                    for_model=request_model,
                    view_kwargs=kwargs,
                    merge_path_parameters=merge_path_parameters,
                )
                or None
            )
            fieldsets: List[str] = []

            # Pydantic validation and casting of inputs
            try:
                # fieldsets for pydantic_enhanced_serializer
                if (
                    body
                    and render_fieldset_model
                    and request_fields_name
                    and request_fields_name in body
                ):
                    fieldsets = body.pop(request_fields_name, [])
                    try:
                        parse_obj_as(Union[str, List[str]], fieldsets)  # type: ignore
                    except ValidationError as e:
                        for error in e.errors():
                            if error["loc"][0] == "__root__":
                                error["loc"] = tuple(
                                    [request_fields_name, *error["loc"][1:]]
                                )
                        raise

                # api input model
                if request_model and request_model_param_name:
                    kwargs[request_model_param_name] = request_model(**body or {})

            except ValidationError as e:
                if current_app.config.get("FLASK_PYDANTIC_API_RENDER_ERRORS", False):
                    response = jsonify({"errors": e.errors()})
                    response.status_code = current_app.config.get(
                        "FLASK_PYDANTIC_API_ERROR_STATUS_CODE", 400
                    )
                    return response

                raise

            if asyncio.iscoroutinefunction(view_func):
                result = async_to_sync(view_func)(*args, **kwargs)
            else:
                result = view_func(*args, **kwargs)

            try:
                if response_models and isinstance(result, dict):
                    result = response_models[0](**result)

                if isinstance(result, BaseModel):
                    if render_fieldset_model:
                        result_data = async_to_sync(render_fieldset_model)(
                            model=result,
                            fieldsets=fieldsets,
                            maximum_expansion_depth=maximum_expansion_depth,
                            raise_error_on_expansion_not_found=False,
                        )
                    else:
                        result_data = result.dict()

                    result = make_response(result_data, success_status_code)

            except ValidationError as e:
                raise Exception(
                    "pydantic model error on api response serialization; "
                    f"endpoint: {request.endpoint}; "
                    f"error: {str(e)}"
                )

            return result

        augment_pydantic_enhanced_serializer_model_schemas(
            request_model, *(response_models or [])
        )

        # Normally wrapping functions with decorators leaves no easy
        # way to tell who is doing the wrapping and for what purpose.
        # This adds some markers that are useful for introspection of
        # endpoints (such as generating schema).
        wrapped_endpoint.__pydantic_api__ = {  # type: ignore
            "name": name,
            "tags": tags,
            "success_status_code": success_status_code,
        }

        return wrapped_endpoint

    return wrap
