import re
from collections import defaultdict
from functools import partial
from typing import Any, Callable, Dict, Optional, Type, Union

from flask import current_app
from openapi_pydantic import Info, MediaType, OpenAPI, Response
from openapi_pydantic.util import PydanticSchema, construct_open_api_with_schema_class
from pydantic import BaseModel

from .api_wrapper import EndpointConfig
from .utils import get_annotated_models, model_has_uploaded_file_type

HTTP_METHODS = set(["get", "post", "patch", "delete", "put"])

model_has_fieldsets_defined: Optional[Callable] = None
try:
    from pydantic_enhanced_serializer.schema import model_has_fieldsets_defined
except ImportError:
    pass


def get_pydantic_api_path_operations() -> Any:
    paths: Dict[str, dict] = defaultdict(dict)

    for rule in current_app.url_map.iter_rules():
        view_func = current_app.view_functions[rule.endpoint]
        view_func_config: Optional[EndpointConfig] = getattr(
            view_func, "__pydantic_api__", None
        )

        if not view_func_config:
            continue

        if not rule.methods:
            continue

        path = re.sub(r"<([\w_]+)>", "{\\1}", rule.rule)

        parameters = []
        request_body: Optional[Dict[str, Any]] = None
        responses: Dict[str, dict] = {}

        success_status_code = str(view_func_config.success_status_code)

        request_model_param_name, request_model, response_models = get_annotated_models(
            view_func
        )

        need_fields_parameter = bool(
            model_has_fieldsets_defined
            and response_models
            and model_has_fieldsets_defined(response_models[0])
        )

        if request_model:
            title = request_model.model_config.get("title") or request_model.__name__
            content_type = (
                "multipart/form-data"
                if model_has_uploaded_file_type(request_model)
                else "application/json"
            )

            if need_fields_parameter:
                current_schema_extra: Union[
                    Callable, dict, None
                ] = request_model.model_config.get("json_schema_extra", None)

                request_model.model_config["json_schema_extra"] = partial(
                    request_body_add_fields_extra_schema, current_schema_extra
                )

            request_body = {
                "description": f"A {title}",
                "content": {
                    content_type: {
                        "schema": PydanticSchema(schema_class=request_model, enum=None)
                    }
                },
                "required": True,
            }

        if response_models:
            title = (
                response_models[0].model_config.get("title")
                or response_models[0].__name__
            )

            responses[success_status_code] = {
                "description": f"A {title}",
                "content": {
                    "application/json": {
                        "schema": PydanticSchema(
                            schema_class=response_models[0], enum=None
                        )
                    }
                },
            }

        else:
            responses[success_status_code] = {
                "description": "Empty Response",
            }

        # path parameters
        for name in view_func.__annotations__.keys():
            if (
                name in rule.arguments
                and name != request_model_param_name
                and name != "return"
            ):
                parameters.append(
                    {
                        "name": name,
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "string",
                        },
                    }
                )

        if success_status_code not in responses:
            responses[success_status_code] = {"description": None}

        for method in rule.methods:
            method = method.lower()
            if method not in HTTP_METHODS:
                continue

            if method.lower() == "get" and need_fields_parameter and not request_body:
                parameters.append(
                    {
                        "name": "fields",
                        "description": (
                            "Comma separated list of fields, fieldset and/or "
                            "expansions to return in the response"
                        ),
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                        },
                    }
                )

            paths[path][method] = {
                "summary": view_func_config.name,
                "requestBody": request_body,
                "tags": view_func_config.tags or [],
                "parameters": parameters,
                "responses": responses,
            }

            if view_func_config.openapi_schema_extra:
                _deep_update(paths[path][method], view_func_config.openapi_schema_extra)

    return paths


def add_response_schema(
    openapi: OpenAPI, status_code: str, schema: Type[BaseModel]
) -> OpenAPI:
    if not openapi.paths:
        return openapi

    title = schema.model_config.get("title") or schema.__name__

    for path_item in openapi.paths.values():
        for method in HTTP_METHODS:
            operation = getattr(path_item, method, None)
            if not operation:
                continue

            if status_code not in operation.responses:
                operation.responses[status_code] = Response(
                    description=f"A {title}",
                    content={
                        "application/json": MediaType(
                            schema=PydanticSchema(schema_class=schema, enum=None)
                        )
                    },
                )

    return construct_open_api_with_schema_class(openapi)


def get_openapi_schema(info: Optional[Info] = None, **kwargs: Any) -> OpenAPI:
    if not info:
        info = Info(
            title="API Documentation",
            version="0.1",
        )
    paths = get_pydantic_api_path_operations()

    return construct_open_api_with_schema_class(
        OpenAPI(
            info=info,
            paths=paths,
            **kwargs,
        )
    )


def request_body_add_fields_extra_schema(
    original_schema_extra: Union[Callable, dict, None],
    schema: Dict[str, Any],
    model: Type[BaseModel],
) -> None:
    if "properties" not in schema:
        schema["properties"] = {}

    if "fields" not in schema["properties"]:
        schema["properties"]["fields"] = {
            "title": "fields",
            "description": "List of fields, fieldset and/or expansions to return in the response",
            "type": "array",
            "items": {
                "type": "string",
            },
        }

    if callable(original_schema_extra):
        _deep_update(schema, original_schema_extra(schema, model) or {})

    elif isinstance(original_schema_extra, dict):
        _deep_update(schema, original_schema_extra)


def _deep_update(into_dict: Dict[Any, Any], from_dict: Dict[Any, Any]) -> None:
    for key in from_dict.keys():
        if (
            key in into_dict
            and isinstance(from_dict[key], dict)
            and isinstance(into_dict[key], dict)
        ):
            _deep_update(into_dict[key], from_dict[key])
        elif (
            key in into_dict
            and isinstance(from_dict[key], list)
            and isinstance(into_dict[key], list)
        ):
            into_dict[key].extend(from_dict[key])
        else:
            into_dict[key] = from_dict[key]
