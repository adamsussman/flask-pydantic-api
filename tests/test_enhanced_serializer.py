from typing import ClassVar

from flask import Flask
from pydantic import BaseModel
from pydantic_enhanced_serializer import FieldsetConfig

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
