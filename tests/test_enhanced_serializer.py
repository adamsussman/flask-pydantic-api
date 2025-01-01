from typing import Any, ClassVar

from flask import Flask
from pydantic import BaseModel
from pydantic_enhanced_serializer import FieldsetConfig, ModelExpansion

from flask_pydantic_api import pydantic_api


def test_validate_fieldsets() -> None:
    class Body(BaseModel):
        field1: str
        field2: str

    app = Flask("test_app")

    @app.post("/")
    @pydantic_api()
    def do_work(body: Body) -> Body:
        return body

    body_in = {
        "field1": "value1",
        "field2": "value2",
        "fields": {"foo": "bar"},
    }

    app.config["FLASK_PYDANTIC_API_RENDER_ERRORS"] = True
    client = app.test_client()
    response = client.post("/", json=body_in)

    # No config to serialize errors
    assert response.status_code == 400, response.json
    assert response.json

    assert len(response.json["errors"]) == 1
    assert response.json["errors"][0]["loc"] == ["fields"]
    assert response.json["errors"][0]["msg"] == "Input should be a valid list"
    assert response.json["errors"][0]["type"] == "list_type"


def test_validate_honor_fields() -> None:
    class Body(BaseModel):
        field1: str
        field2: str

        fieldset_config: ClassVar = FieldsetConfig(
            fieldsets={
                "default": [],
            }
        )

    app = Flask("test_app")

    @app.post("/")
    @pydantic_api()
    def do_work(body: Body) -> Body:
        return body

    body_in = {
        "field1": "value1",
        "field2": "value2",
        "fields": ["field2"],
    }

    client = app.test_client()
    response = client.post("/", json=body_in)

    # No config to serialize errors
    assert response.status_code == 200, response.json
    assert response.json

    assert response.json == {"field2": "value2"}


def test_expansion_with_nested_internal_request_and_context() -> None:

    class OuterResponse(BaseModel):
        field1: str
        field2: str

        fieldset_config: ClassVar = FieldsetConfig(
            fieldsets={
                "default": ["*"],
                "field3": ModelExpansion(
                    response_model=dict, expansion_method_name="get_nested_data"
                ),
            }
        )

        def get_nested_data(self, context: Any) -> Any:
            from flask import current_app

            client = current_app.test_client()
            response = client.get("/inner")
            assert response.status_code == 200
            assert response.json
            assert response.json == {
                "inner_field1": "inner1",
                "inner_field2": "inner2",
                "inner_field3": "inner3",
            }

            return response.json

    class InnerResponse(BaseModel):
        inner_field1: str
        inner_field2: str

        fieldset_config: ClassVar = FieldsetConfig(
            fieldsets={
                "default": ["*"],
                "inner_field3": ModelExpansion(
                    expansion_method_name="get_inner_field",
                ),
            }
        )

        def get_inner_field(self, context=Any) -> str:
            from flask import current_app, request

            assert current_app
            assert request
            assert request.path == "/inner"

            return "inner3"

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    def do_outer_work() -> OuterResponse:
        return OuterResponse(
            field1="value1",
            field2="value2",
        )

    @app.get("/inner")
    @pydantic_api()
    def do_inner_work() -> InnerResponse:
        return InnerResponse(
            inner_field1="inner1",
            inner_field2="inner2",
        )

    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200, response.json
    assert response.json

    assert response.json == {
        "field1": "value1",
        "field2": "value2",
        "field3": {
            "inner_field1": "inner1",
            "inner_field2": "inner2",
            "inner_field3": "inner3",
        },
    }
