import json
from textwrap import dedent
from typing import ClassVar, Optional, Union

import pytest
from flask import Flask
from pydantic import BaseModel

import flask_pydantic_api.apidocs_views
from flask_pydantic_api import UploadedFile, pydantic_api
from flask_pydantic_api.openapi import add_response_schema, get_openapi_schema
from tests.utils import require_serializer

try:  # Ensure pytest can parse the file without the import
    from pydantic_enhanced_serializer import FieldsetConfig
except ImportError:
    pass


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

    result_json = json.dumps(
        result,
        indent=4,
        sort_keys=True,
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

    result_json = json.dumps(
        result,
        indent=4,
        sort_keys=True,
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
        result = get_openapi_schema()

    assert "ThisResponse" in result["components"]["schemas"]
    assert (
        "this_field1" in result["components"]["schemas"]["ThisResponse"]["properties"]
    )
    assert "/api/foo/bar" in result["paths"]
    assert (
        result["paths"]["/api/foo/bar"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/ThisResponse"
    )


def test_union_type_response_object(basic_app: Flask) -> None:
    class ThisResponse(BaseModel):
        this_field1: str

    @basic_app.get("/api/foo/bar")
    @pydantic_api()
    def get_something() -> dict | ThisResponse:
        return {"field1": "bar"}

    with basic_app.app_context():
        result = get_openapi_schema()

    assert "ThisResponse" in result["components"]["schemas"]
    assert (
        "this_field1" in result["components"]["schemas"]["ThisResponse"]["properties"]
    )
    assert "/api/foo/bar" in result["paths"]
    assert (
        result["paths"]["/api/foo/bar"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
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
        result = get_openapi_schema()

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
        result = get_openapi_schema()

    assert "arg1" in [
        param["name"] for param in result["paths"]["/foo/{arg1}"]["get"]["parameters"]
    ]
    assert "arg1" not in result["components"]["schemas"]["Body"]["properties"]


def test_path_args_typed(basic_app: Flask) -> None:
    class Body(BaseModel):
        field1: str

    @basic_app.get("/foo/<int:arg1>/bar/<arg2>/baz/<int(signed=True):arg3>")
    @pydantic_api()
    def get_foo(arg1: int, arg2: str, arg3: int, body: Body) -> Body:
        return body

    with basic_app.app_context():
        result = get_openapi_schema()

    params = result["paths"]["/foo/{arg1}/bar/{arg2}/baz/{arg3}"]["get"]["parameters"]
    param_schemas = {param["name"]: param["schema"] for param in params}
    assert param_schemas == {
        "arg1": {"type": "integer", "minimum": 0},
        "arg2": {"type": "string"},
        "arg3": {"type": "integer"},
    }


@require_serializer
def test_fieldsets_added_to_query_string(basic_app: Flask) -> None:
    class ResponseModel(BaseModel):
        field1: str

        fieldset_config: ClassVar = FieldsetConfig(
            fieldsets={
                "default": ["*"],
            }
        )

    @basic_app.get("/")
    @pydantic_api()
    def get_foo() -> ResponseModel:
        return ResponseModel(field1="Foo")

    with basic_app.app_context():
        result = get_openapi_schema()

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
    assert fields_field["in"] == "query"
    assert fields_field["required"] is False
    assert fields_field["schema"]["type"] == "string"


@require_serializer
def test_fieldsets_added_to_request_body(basic_app: Flask) -> None:
    class Body(BaseModel):
        field1: str

    class ResponseModel(BaseModel):
        field1: str

        fieldset_config: ClassVar = FieldsetConfig(
            fieldsets={
                "default": ["*"],
            }
        )

    @basic_app.post("/")
    @pydantic_api()
    def post_foo(body: Body) -> ResponseModel:
        return ResponseModel(field1=body.field1)

    with basic_app.app_context():
        result = get_openapi_schema()

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
                            "schema": {
                                "type": "string",
                                "format": "binary",
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
        result = get_openapi_schema()

    assert (
        result["paths"]["/"]["post"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        == "#/components/schemas/Body"
    )
    assert (
        result["paths"]["/"]["post"]["responses"]["200"]["content"]["image/*"][
            "schema"
        ]["type"]
        == "string"
    )
    assert (
        result["paths"]["/"]["post"]["responses"]["200"]["content"]["image/*"][
            "schema"
        ]["format"]
        == "binary"
    )


def test_union_response_different_status_code() -> None:
    class ResponseA(BaseModel):
        field1: str

    class ResponseB(BaseModel):
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api(
        success_status_code_by_response_model={
            ResponseA: 200,
            ResponseB: 202,
        }
    )
    def do_work() -> Union[ResponseA, ResponseB]:
        return ResponseA(field1="val1")

    with app.app_context():
        result = get_openapi_schema()

    assert (
        result["paths"]["/"]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        == "#/components/schemas/ResponseA"
    )

    assert (
        result["paths"]["/"]["get"]["responses"]["202"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        == "#/components/schemas/ResponseB"
    )

    assert "ResponseA" in result["components"]["schemas"]
    assert "ResponseB" in result["components"]["schemas"]


def test_union_response_same_status_code() -> None:
    class ResponseA(BaseModel):
        field1: str

    class ResponseB(BaseModel):
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    def do_work() -> Union[ResponseA, ResponseB]:
        return ResponseA(field1="val1")

    with app.app_context():
        result = get_openapi_schema()

    assert result["paths"]["/"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {
        "oneOf": [
            {"$ref": "#/components/schemas/ResponseA"},
            {"$ref": "#/components/schemas/ResponseB"},
        ]
    }


def test_union_type_response_same_status_code() -> None:
    class ResponseA(BaseModel):
        field1: str

    class ResponseB(BaseModel):
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    def do_work() -> ResponseA | ResponseB:
        return ResponseA(field1="val1")

    with app.app_context():
        result = get_openapi_schema()

    assert result["paths"]["/"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {
        "oneOf": [
            {"$ref": "#/components/schemas/ResponseA"},
            {"$ref": "#/components/schemas/ResponseB"},
        ]
    }


def test_model_and_uploader_request_body() -> None:
    class FileRequest(BaseModel):
        file1: UploadedFile
        other_var: str

    class OtherRequest(BaseModel):
        val1: str

    app = Flask("test_app")

    @app.post("/")
    @pydantic_api()
    def do_work(body: Union[FileRequest, OtherRequest]) -> dict:
        return {}

    with app.app_context():
        result = get_openapi_schema()

    assert result["paths"]["/"]["post"]["requestBody"] == {
        "content": {
            "application/json": {
                "schema": {
                    "$ref": "#/components/schemas/OtherRequest",
                }
            },
            "multipart/form-data": {
                "schema": {
                    "$ref": "#/components/schemas/FileRequest",
                }
            },
        },
        "description": "A FileRequest or OtherRequest",
        "required": True,
    }

    assert "FileRequest" in result["components"]["schemas"]
    assert "OtherRequest" in result["components"]["schemas"]


def test_model_and_uploader_request_body_with_union_type() -> None:
    class FileRequest(BaseModel):
        file1: UploadedFile
        other_var: str

    class OtherRequest(BaseModel):
        val1: str

    app = Flask("test_app")

    @app.post("/")
    @pydantic_api()
    def do_work(body: FileRequest | OtherRequest) -> dict:
        return {}

    with app.app_context():
        result = get_openapi_schema()

    assert result["paths"]["/"]["post"]["requestBody"] == {
        "content": {
            "application/json": {
                "schema": {
                    "$ref": "#/components/schemas/OtherRequest",
                }
            },
            "multipart/form-data": {
                "schema": {
                    "$ref": "#/components/schemas/FileRequest",
                }
            },
        },
        "description": "A FileRequest or OtherRequest",
        "required": True,
    }

    assert "FileRequest" in result["components"]["schemas"]
    assert "OtherRequest" in result["components"]["schemas"]


def test_request_model_exploded_in_query_string() -> None:
    class Params(BaseModel):
        var1: str
        var2: Optional[int] = None

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api(get_request_model_from_query_string=True)
    def do_work(body: Params) -> dict:
        return {}

    with app.app_context():
        result = get_openapi_schema()

    assert "requestBody" not in result["paths"]["/"]["get"]
    assert result["paths"]["/"]["get"]["parameters"] == [
        {
            "in": "query",
            "type": "form",
            "explode": "true",
            "schema": {
                "$ref": "#/components/schemas/Params",
            },
        }
    ]
    assert "Params" in result["components"]["schemas"]


EXPECTED_DESCRIPTION = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit,\n"
    "sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\n"
    "\n"
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris\n"
    "nisi ut aliquip ex ea commodo consequat."
)


def test_name_and_description_in_decorator(basic_app: Flask) -> None:
    class Body(BaseModel):
        field1: str

    @basic_app.get("/foo")
    @pydantic_api(
        name="Calculate The Foo",
        description="""
            Lorem ipsum dolor sit amet, consectetur adipiscing elit,
            sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

            Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris
            nisi ut aliquip ex ea commodo consequat.
        """,
    )
    def get_foo() -> Body:
        """Get the foo docstring."""
        return Body(field1="foo")

    with basic_app.app_context():
        result = get_openapi_schema()

    assert result["paths"]["/foo"]["get"]["summary"] == "Calculate The Foo"
    assert result["paths"]["/foo"]["get"]["description"] == EXPECTED_DESCRIPTION


def test_default_name_from_function_name(basic_app: Flask) -> None:
    class Body(BaseModel):
        field1: str

    @basic_app.get("/foo")
    @pydantic_api()
    def get_foo() -> Body:
        """
        Lorem ipsum dolor sit amet, consectetur adipiscing elit,
        sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

        Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris
        nisi ut aliquip ex ea commodo consequat.
        """
        return Body(field1="foo")

    basic_app.config["FLASK_PYDANTIC_API_NAME_FROM_FUNCTION"] = True

    with basic_app.app_context():
        result = get_openapi_schema()

    assert result["paths"]["/foo"]["get"]["summary"] == "Get Foo"


def test_default_description_from_function_docstring(basic_app: Flask) -> None:
    class Body(BaseModel):
        field1: str

    @basic_app.get("/foo")
    @pydantic_api()
    def get_foo() -> Body:
        """
        Lorem ipsum dolor sit amet, consectetur adipiscing elit,
        sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

        Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris
        nisi ut aliquip ex ea commodo consequat.
        """
        return Body(field1="foo")

    basic_app.config["FLASK_PYDANTIC_API_DESCRIPTION_FROM_DOCSTRING"] = True

    with basic_app.app_context():
        result = get_openapi_schema()

    assert result["paths"]["/foo"]["get"]["description"] == EXPECTED_DESCRIPTION


def test_empty_name_and_description(basic_app: Flask) -> None:
    class Body(BaseModel):
        field1: str

    @basic_app.get("/foo")
    @pydantic_api()
    def get_foo() -> Body:
        """Lorem ipsum dolor sit amet."""
        return Body(field1="foo")

    with basic_app.app_context():
        result = get_openapi_schema()

    assert "summary" not in result["paths"]["/foo"]["get"]
    assert "description" not in result["paths"]["/foo"]["get"]
