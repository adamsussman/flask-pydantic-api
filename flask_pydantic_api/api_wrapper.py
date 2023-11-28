import asyncio
from functools import wraps
from inspect import isclass
from itertools import chain
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, get_origin

from asgiref.sync import async_to_sync
from flask import abort, current_app, jsonify, make_response, request
from pydantic import BaseModel, TypeAdapter, ValidationError

from .utils import (
    function_has_fields_in_signature,
    get_annotated_models,
    model_has_uploaded_file_type,
)

augment_schema_with_fieldsets: Optional[Callable] = None
render_fieldset_model: Optional[Callable] = None

try:
    from pydantic_enhanced_serializer import render_fieldset_model
except ImportError:
    pass


class EndpointConfig(BaseModel):
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    openapi_schema_extra: Optional[Dict[str, Any]] = None
    success_status_code: int
    request_fields_name: str
    model_dump_kwargs: Optional[Dict[str, Any]] = None


def get_request_args(
    view_kwargs: Dict[str, Any],
    for_model: Optional[Type[BaseModel]] = None,
    merge_path_parameters: Optional[bool] = False,
    request_model_param_name: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    args: Dict[str, Any] = {}

    if for_model and model_has_uploaded_file_type(for_model):
        if not request.content_type.lower().startswith("multipart/form-data"):
            abort(415, "multipart/form-data expected")

        for name, value in chain(request.files.items(), request.form.items()):
            args[name] = value

    elif request.is_json and request.json:
        args.update(request.json)

    elif request.query_string:
        args.update(request.args.to_dict())
        if for_model:
            args.update(
                {
                    k: v
                    for k, v in request.args.to_dict(flat=False).items()
                    if k in for_model.model_fields
                    and for_model.model_fields[k].annotation
                    and (origin := get_origin(for_model.model_fields[k].annotation))
                    and isclass(origin)
                    and issubclass(origin, (list, set, frozenset, dict))
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


# decorator that can be composed with regular Flask @blueprint.get/post/etc decorators.
# This decorator uses type signatures to figure out the request and response pydantic models.
def pydantic_api(
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    success_status_code: int = 200,
    maximum_expansion_depth=5,
    request_fields_name: str = "fields",
    merge_path_parameters: bool = False,
    openapi_schema_extra: Optional[Dict[str, Any]] = None,
    model_dump_kwargs: Optional[Dict[str, Any]] = None,
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
                    request_model_param_name=request_model_param_name,
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
                    fieldsets_input = body.pop(request_fields_name, [])
                    fieldsets = (
                        fieldsets_input.split(",")
                        if isinstance(fieldsets_input, str)
                        else fieldsets_input
                    )
                    adapter = TypeAdapter(Dict[str, List[str]])
                    adapter.validate_python({request_fields_name: fieldsets})

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

            if function_has_fields_in_signature(view_func, request_fields_name):
                kwargs[request_fields_name] = fieldsets

            try:
                if asyncio.iscoroutinefunction(view_func):
                    result = async_to_sync(view_func)(*args, **kwargs)
                else:
                    result = view_func(*args, **kwargs)

                if response_models and isinstance(result, dict):
                    result = response_models[0](**result)

                if isinstance(result, BaseModel):
                    if render_fieldset_model:
                        result_data = async_to_sync(render_fieldset_model)(
                            model=result,
                            fieldsets=fieldsets,
                            maximum_expansion_depth=maximum_expansion_depth,
                            raise_error_on_expansion_not_found=False,
                            **(model_dump_kwargs or {}),
                        )
                    else:
                        result_data = result.model_dump_json(
                            **(model_dump_kwargs or {}),
                        )

                    result = make_response(result_data, success_status_code)

            except ValidationError as e:
                raise Exception(
                    "pydantic model error on api response serialization; "
                    f"endpoint: {request.endpoint}; "
                    f"error: {str(e)}"
                )

            return result

        # Normally wrapping functions with decorators leaves no easy
        # way to tell who is doing the wrapping and for what purpose.
        # This adds some markers that are useful for introspection of
        # endpoints (such as generating schema).
        wrapped_endpoint.__pydantic_api__ = EndpointConfig(  # type: ignore
            name=name,
            tags=tags,
            success_status_code=success_status_code,
            request_fields_name=request_fields_name,
            openapi_schema_extra=openapi_schema_extra,
            model_dump_kwargs=model_dump_kwargs,
        )

        return wrapped_endpoint

    return wrap
