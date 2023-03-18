import json
from textwrap import dedent

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
