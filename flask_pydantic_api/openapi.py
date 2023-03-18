import re
from collections import defaultdict
from typing import Any, Dict, Optional, Type

from flask import current_app
from openapi_schema_pydantic import Info, MediaType, OpenAPI, Response
from openapi_schema_pydantic.util import (
    PydanticSchema,
    construct_open_api_with_schema_class,
)
from pydantic import BaseModel

HTTP_METHODS = set(["get", "post", "patch", "delete", "put"])


def get_pydantic_api_path_operations() -> Any:
    paths: Dict[str, dict] = defaultdict(dict)

    for rule in current_app.url_map.iter_rules():
        view_func = current_app.view_functions[rule.endpoint]
        if not getattr(view_func, "__pydantic_api__", None):
            continue

        if not rule.methods:
            continue

        path = re.sub(r"<([\w_]+)>", "{\\1}", rule.rule)

        parameters = []
        request_body = None
        responses: Dict[str, dict] = {}

        success_status_code = str(
            view_func.__pydantic_api__.get("success_status_code", "200")  # type: ignore
        )

        for name, obj in view_func.__annotations__.items():
            if issubclass(obj, BaseModel):
                title = obj.__config__.title or obj.__name__

                body: Dict[str, Any] = {
                    "description": f"A {title}",
                    "content": {
                        "application/json": {"schema": PydanticSchema(schema_class=obj)}
                    },
                }

                if name == "return":
                    responses[success_status_code] = body

                else:
                    body["required"] = True
                    request_body = body

            elif name in rule.arguments:
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

            paths[path][method] = {
                "summary": view_func.__pydantic_api__.get("name"),  # type: ignore
                "requestBody": request_body,
                "tags": view_func.__pydantic_api__.get("tags") or [],  # type: ignore
                "parameters": parameters,
                "responses": responses,
            }

    return paths


def add_response_schema(
    openapi: OpenAPI, status_code: str, schema: Type[BaseModel]
) -> OpenAPI:
    if not openapi.paths:
        return openapi

    title = schema.__config__.title or schema.__name__

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
                            schema=PydanticSchema(schema_class=schema)
                        )
                    },
                )

    return construct_open_api_with_schema_class(openapi)


def get_openapi_schema(info: Optional[Info] = None) -> OpenAPI:
    if not info:
        info = Info(
            title="API Documentation",
            version="0.1",
        )
    paths = get_pydantic_api_path_operations()

    return construct_open_api_with_schema_class(
        OpenAPI.parse_obj(
            {
                "info": info,
                "paths": paths,
            }
        )
    )
