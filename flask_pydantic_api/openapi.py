import re
from collections import defaultdict
from functools import partial
from typing import Any, Callable, Dict, Optional, Tuple, Type, Union

from flask import current_app
from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema

from .api_wrapper import EndpointConfig
from .utils import get_annotated_models, model_has_uploaded_file_type

HTTP_METHODS = set(["get", "post", "patch", "delete", "put"])

model_has_fieldsets_defined: Optional[Callable] = None
try:
    from pydantic_enhanced_serializer.schema import (
        FieldsetGenerateJsonSchema,
        model_has_fieldsets_defined,
    )
except ImportError:
    model_has_fieldsets_defined = None


def get_pydantic_api_path_operations(
    schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    paths: Dict[str, dict] = defaultdict(dict)
    components: Dict[str, dict] = {}

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
        success_status_code_by_response_model = (
            view_func_config.success_status_code_by_response_model
        )

        request_model_param_name, request_models, response_models = (
            get_annotated_models(view_func)
        )

        need_fields_parameter = bool(
            model_has_fieldsets_defined
            and response_models
            and model_has_fieldsets_defined(response_models[0])
        )

        if request_models:
            for request_model in request_models:
                title = (
                    request_model.model_config.get("title") or request_model.__name__
                )
                content_type = (
                    "multipart/form-data"
                    if model_has_uploaded_file_type(request_model)
                    else "application/json"
                )

                if need_fields_parameter:
                    current_schema_extra: Union[Callable, dict, None] = (
                        request_model.model_config.get("json_schema_extra", None)
                    )

                    request_model.model_config["json_schema_extra"] = partial(
                        request_body_add_fields_extra_schema, current_schema_extra
                    )

                schema = request_model.model_json_schema(
                    mode="validation",
                    ref_template="#/components/schemas/{model}",
                    schema_generator=schema_generator,
                )
                components.update(schema.pop("$defs", {}))
                components[title] = schema

                if request_body:
                    request_body["description"] = " or ".join(
                        [request_body["description"], title]
                    )
                    request_body["content"][content_type] = {
                        "schema": {"$ref": f"#/components/schemas/{title}"}
                    }

                elif view_func_config.get_request_model_from_query_string:
                    request_body = {"schema": {"$ref": f"#/components/schemas/{title}"}}
                else:
                    request_body = {
                        "description": f"A {title}",
                        "content": {
                            content_type: {
                                "schema": {"$ref": f"#/components/schemas/{title}"}
                            }
                        },
                        "required": True,
                    }

        if response_models:
            for response_model in response_models:
                title = (
                    response_model.model_config.get("title") or response_model.__name__
                )

                schema = response_model.model_json_schema(
                    mode="serialization",
                    ref_template="#/components/schemas/{model}",
                    schema_generator=schema_generator,
                )
                components.update(schema.pop("$defs", {}))
                components[title] = schema

                status_code = str(success_status_code)
                if success_status_code_by_response_model:
                    status_code = str(
                        success_status_code_by_response_model.get(
                            response_model, success_status_code
                        )
                    )

                if status_code in responses:
                    # status already there, need to append
                    if (
                        "oneOf"
                        not in responses[status_code]["content"]["application/json"][
                            "schema"
                        ]
                    ):
                        responses[status_code]["content"]["application/json"][
                            "schema"
                        ] = {
                            "oneOf": [
                                responses[status_code]["content"]["application/json"][
                                    "schema"
                                ]
                            ]
                        }

                    responses[status_code]["content"]["application/json"]["schema"][
                        "oneOf"
                    ].append({"$ref": f"#/components/schemas/{title}"})
                    responses[status_code]["description"] = " or ".join(
                        [responses[status_code]["description"], title]
                    )
                else:
                    responses[status_code] = {
                        "description": f"A {title}",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/{title}"}
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
                "tags": view_func_config.tags or [],
                "parameters": parameters,
                "responses": responses,
            }
            if request_body:
                if view_func_config.get_request_model_from_query_string:
                    paths[path][method]["parameters"].append(
                        {
                            "in": "query",
                            "type": "form",
                            "explode": "true",
                            **request_body,
                        }
                    )
                else:
                    paths[path][method]["requestBody"] = request_body

            if view_func_config.name:
                paths[path][method]["summary"] = view_func_config.name

            if view_func_config.openapi_schema_extra:
                _deep_update(paths[path][method], view_func_config.openapi_schema_extra)

    return paths, components


def add_response_schema(
    openapi: Dict[str, Any],
    status_code: str,
    model: Type[BaseModel],
    schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
) -> Dict[str, Any]:
    if not openapi.get("paths"):
        return openapi

    if "components" not in openapi:
        openapi["components"] = {}
    if "schemas" not in openapi["components"]:
        openapi["components"]["schemas"] = {}

    title = model.__name__
    json_schema = model.model_json_schema(
        mode="serialization",
        ref_template="#/components/schemas/{model}",
        schema_generator=schema_generator,
    )
    if "$defs" in json_schema:
        openapi["components"]["schemas"].update(json_schema.pop("$defs", {}))

    openapi["components"]["schemas"][title] = json_schema

    for path_item in openapi["paths"].values():
        for method in HTTP_METHODS:
            operation = path_item.get(method, None)
            if not operation:
                continue

            if status_code not in operation.get("responses", {}):
                if "responses" not in operation:
                    operation["responses"] = {}

                operation["responses"][status_code] = {
                    "description": f"A {title}",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{title}"}
                        }
                    },
                }

    return openapi


def get_openapi_schema(
    schema_generator: Optional[type[GenerateJsonSchema]] = None, **kwargs
) -> Dict[str, Any]:
    if schema_generator is None and FieldsetGenerateJsonSchema is not None:
        schema_generator = FieldsetGenerateJsonSchema

    paths, components = get_pydantic_api_path_operations(
        schema_generator=schema_generator
    )

    if "paths" in kwargs:
        paths.update(kwargs.pop("paths"))

    components = {"schemas": components}

    if "components" in kwargs:
        components.update(kwargs.pop("components"))

    if "servers" not in kwargs:
        kwargs["servers"] = [{"url": "/"}]

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "API Documentation",
            "version": "0.1",
        },
        "paths": paths,
        "components": components,
        **kwargs,
    }


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
