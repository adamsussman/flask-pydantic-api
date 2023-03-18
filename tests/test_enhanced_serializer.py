from flask import Flask
from pydantic import BaseModel

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
    assert response.json == {
        "errors": [
            {"loc": ["fields"], "msg": "str type expected", "type": "type_error.str"},
            {
                "loc": ["fields"],
                "msg": "value is not a valid list",
                "type": "type_error.list",
            },
        ]
    }


def test_validate_honor_fields() -> None:
    class Body(BaseModel):
        field1: str
        field2: str

        class Config:
            fieldsets: dict = {
                "default": [],
            }

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
    assert response.json == {"field2": "value2"}
