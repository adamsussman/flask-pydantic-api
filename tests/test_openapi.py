import json
from textwrap import dedent
from typing import Union

import pytest
from flask import Flask
from pydantic import BaseModel

import flask_pydantic_api.apidocs_views
from flask_pydantic_api import pydantic_api
from flask_pydantic_api.openapi import add_response_schema, get_openapi_schema


@pytest.fixture
def basic_app() -> Flask:
    class Response(BaseModel):
        field1: str
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    def do_work() -> Response:
        return Response(
            field1="field1 value",
            field2="field2 value",
        )

    return app


def test_basic_schema(basic_app: Flask) -> None:
    with basic_app.app_context():
        result = get_openapi_schema()

    result_json = result.json(
        by_alias=True, exclude_none=True, indent=4, sort_keys=True
    )
    assert (
        result_json
        == dedent(
            """
        {
            "components": {
                "schemas": {
                    "Response": {
                        "properties": {
                            "field1": {
                                "title": "Field1",
                                "type": "string"
                            },
                            "field2": {
                                "title": "Field2",
                                "type": "string"
                            }
                        },
                        "required": [
                            "field1",
                            "field2"
                        ],
                        "title": "Response",
                        "type": "object"
                    }
                }
            },
            "info": {
                "title": "API Documentation",
                "version": "0.1"
            },
            "openapi": "3.1.0",
            "paths": {
                "/": {
                    "get": {
                        "deprecated": false,
                        "parameters": [],
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/Response"
                                        }
                                    }
                                },
                                "description": "A Response"
                            }
                        },
                        "tags": []
                    }
                }
            },
            "servers": [
                {
                    "url": "/"
                }
            ]
        }
    """
        ).strip()
    )


def test_add_error_response(basic_app: Flask) -> None:
    class SpecialError(BaseModel):
        error_code: str
        error_description: str

    with basic_app.app_context():
        result = get_openapi_schema()
        result = add_response_schema(result, "400", SpecialError)

    result_json = result.json(
        by_alias=True, exclude_none=True, indent=4, sort_keys=True
    )
    assert (
        result_json
        == dedent(
            """
        {
            "components": {
                "schemas": {
                    "Response": {
                        "properties": {
                            "field1": {
                                "title": "Field1",
                                "type": "string"
                            },
                            "field2": {
                                "title": "Field2",
                                "type": "string"
                            }
                        },
                        "required": [
                            "field1",
                            "field2"
                        ],
                        "title": "Response",
                        "type": "object"
                    },
                    "SpecialError": {
                        "properties": {
                            "error_code": {
                                "title": "Error Code",
                                "type": "string"
                            },
                            "error_description": {
                                "title": "Error Description",
                                "type": "string"
                            }
                        },
                        "required": [
                            "error_code",
                            "error_description"
                        ],
                        "title": "SpecialError",
                        "type": "object"
                    }
                }
            },
            "info": {
                "title": "API Documentation",
                "version": "0.1"
            },
            "openapi": "3.1.0",
            "paths": {
                "/": {
                    "get": {
                        "deprecated": false,
                        "parameters": [],
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/Response"
                                        }
                                    }
                                },
                                "description": "A Response"
                            },
                            "400": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/SpecialError"
                                        }
                                    }
                                },
                                "description": "A SpecialError"
                            }
                        },
                        "tags": []
                    }
                }
            },
            "servers": [
                {
                    "url": "/"
                }
            ]
        }
    """
        ).strip()
    )


def test_apidocs_get_spec(basic_app: Flask) -> None:
    basic_app.register_blueprint(
        flask_pydantic_api.apidocs_views.blueprint, url_prefix="/apidocs/"
    )

    with basic_app.test_client() as client:
        result = client.get("/apidocs/openapi.json")
        assert result.status_code == 200
        assert result.content_type == "application/json"

        schema = json.loads(result.text)
        assert "openapi" in schema
        assert (
            schema["paths"]["/"]["get"]["responses"]["200"]["description"]
            == "A Response"
        )


def test_apidocs_get_viewer(basic_app: Flask) -> None:
    basic_app.register_blueprint(
        flask_pydantic_api.apidocs_views.blueprint, url_prefix="/apidocs"
    )

    with basic_app.test_client() as client:
        result = client.get("/apidocs/")
        assert result.status_code == 200
        assert result.content_type.startswith("text/html")

        assert "rapidoc" in result.text


def test_union_response_object(basic_app: Flask) -> None:
    class ThisResponse(BaseModel):
        this_field1: str

    @basic_app.get("/api/foo/bar")
    @pydantic_api()
    def get_something() -> Union[dict, ThisResponse]:
        return {"field1": "bar"}

    with basic_app.app_context():
        result = get_openapi_schema().dict()

    assert "ThisResponse" in result["components"]["schemas"]
    assert (
        "this_field1" in result["components"]["schemas"]["ThisResponse"]["properties"]
    )
    assert "/api/foo/bar" in result["paths"]
    assert (
        result["paths"]["/api/foo/bar"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["media_type_schema"]["ref"]
        == "#/components/schemas/ThisResponse"
    )


def test_path_args_merge(basic_app: Flask) -> None:
    class Body(BaseModel):
        arg1: str
        field1: str

    @basic_app.get("/foo/<arg1>")
    @pydantic_api()
    def get_foo(arg1: str, body: Body) -> Body:
        return body

    with basic_app.app_context():
        result = get_openapi_schema().dict()

    assert "arg1" in [
        param["name"] for param in result["paths"]["/foo/{arg1}"]["get"]["parameters"]
    ]
    assert "arg1" in result["components"]["schemas"]["Body"]["properties"]


def test_path_args_keep(basic_app: Flask) -> None:
    class Body(BaseModel):
        field1: str

    @basic_app.get("/foo/<arg1>")
    @pydantic_api()
    def get_foo(arg1: str, body: Body) -> Body:
        return body

    with basic_app.app_context():
        result = get_openapi_schema().dict()

    assert "arg1" in [
        param["name"] for param in result["paths"]["/foo/{arg1}"]["get"]["parameters"]
    ]
    assert "arg1" not in result["components"]["schemas"]["Body"]["properties"]


def test_fieldsets_added_to_query_string(basic_app: Flask) -> None:
    class ResponseModel(BaseModel):
        field1: str

        class Config:
            fieldsets = {
                "default": ["*"],
            }

    @basic_app.get("/")
    @pydantic_api()
    def get_foo() -> ResponseModel:
        return ResponseModel(field1="Foo")

    with basic_app.app_context():
        result = get_openapi_schema().dict()

    fields_field = next(
        iter(
            [
                param
                for param in result["paths"]["/"]["get"]["parameters"]
                if param["name"] == "fields"
            ]
        )
    )
    assert fields_field
    assert fields_field["name"] == "fields"
    assert fields_field["param_in"] == "query"
    assert fields_field["required"] is False
    assert fields_field["param_schema"]["type"] == "string"


def test_fieldsets_added_to_request_body(basic_app: Flask) -> None:
    class Body(BaseModel):
        field1: str

    class ResponseModel(BaseModel):
        field1: str

        class Config:
            fieldsets = {
                "default": ["*"],
            }

    @basic_app.post("/")
    @pydantic_api()
    def post_foo(body: Body) -> ResponseModel:
        return ResponseModel(field1=body.field1)

    with basic_app.app_context():
        result = get_openapi_schema().dict()

    fields_field = result["components"]["schemas"]["Body"]["properties"]["fields"]
    assert fields_field
    assert fields_field["title"] == "fields"
    assert fields_field["type"] == "array"
    assert fields_field["items"]["type"] == "string"
    assert "fields" not in result["components"]["schemas"]["Body"]["required"]


def test_extra_schema(basic_app: Flask) -> None:
    class Body(BaseModel):
        field1: str

    @basic_app.post("/")
    @pydantic_api(
        openapi_schema_extra={
            "responses": {
                "200": {
                    "content": {
                        "image/*": {
                            "media_type_schema": {
                                "type": "string",
                                "schema_format": "binary",
                            }
                        }
                    }
                }
            }
        }
    )
    def post_foo() -> Body:
        return Body(field1="foo")

    with basic_app.app_context():
        result = get_openapi_schema().dict()

    assert (
        result["paths"]["/"]["post"]["responses"]["200"]["content"]["application/json"][
            "media_type_schema"
        ]["ref"]
        == "#/components/schemas/Body"
    )
    assert (
        result["paths"]["/"]["post"]["responses"]["200"]["content"]["image/*"][
            "media_type_schema"
        ]["type"]
        == "string"
    )
    assert (
        result["paths"]["/"]["post"]["responses"]["200"]["content"]["image/*"][
            "media_type_schema"
        ]["schema_format"]
        == "binary"
    )
