from typing import List, Union

from flask import Flask
from pydantic import BaseModel

from flask_pydantic_api import pydantic_api


def test_simple_response() -> None:
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

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200, response.json
    assert response.json == {
        "field1": "field1 value",
        "field2": "field2 value",
    }


def test_echo_post() -> None:
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
    }

    client = app.test_client()
    response = client.post("/", json=body_in)

    assert response.status_code == 200, response.json
    assert response.json == body_in


def test_echo_query_string() -> None:
    class Body(BaseModel):
        field1: str
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    def do_work(body: Body) -> Body:
        return body

    body_in = {
        "field1": "value1",
        "field2": "value2",
    }

    client = app.test_client()
    response = client.get("/", query_string=body_in)

    assert response.status_code == 200, response.json
    assert response.json == body_in


def test_echo_query_string_multi() -> None:
    class Body(BaseModel):
        field1: List[str]
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    def do_work(body: Body) -> Body:
        return body

    body_in = {
        "field1": ["value1a", "value1b"],
        "field2": "value2",
    }

    client = app.test_client()
    response = client.get("/", query_string=body_in)

    assert response.status_code == 200, response.json
    assert response.json == body_in


def test_validate_fail_post() -> None:
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
    }

    client = app.test_client()
    response = client.post("/", json=body_in)

    # No config to serialize errors
    assert response.status_code == 500

    app.config["FLASK_PYDANTIC_API_RENDER_ERRORS"] = True

    response = client.post("/", json=body_in)
    assert response.status_code == 400
    assert response.json

    assert len(response.json["errors"]) == 1
    assert response.json["errors"][0]["loc"] == ["field2"]
    assert response.json["errors"][0]["type"] == "missing"
    assert response.json["errors"][0]["msg"] == "Field required"


def test_body_and_path_vars() -> None:
    class Body(BaseModel):
        field1: str
        field2: str

    app = Flask("test_app")

    @app.post("/foo/<field1>")
    @pydantic_api(merge_path_parameters=True)
    def do_work(body: Body) -> Body:
        return body

    body_in = {
        "field2": "value1",
    }

    client = app.test_client()
    response = client.post("/foo/bar", json=body_in)

    assert response.status_code == 200
    assert response.json == {"field1": "bar", **body_in}


def test_body_and_path_vars_no_merge_args() -> None:
    class Body(BaseModel):
        field2: str

    app = Flask("test_app")

    @app.post("/foo/<field1>")
    @pydantic_api(merge_path_parameters=False)
    def do_work(field1: str, body: Body) -> Body:
        assert field1 == "bar"
        return body

    body_in = {
        "field2": "value1",
    }

    client = app.test_client()
    response = client.post("/foo/bar", json=body_in)

    assert response.status_code == 200
    assert response.json == body_in


def test_response_is_not_model() -> None:
    class Response(BaseModel):
        field1: str
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    async def do_work() -> Union[dict, Response]:
        return {
            "field1": "field1 value",
            "field2": "field2 value",
        }

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200, response.json
    assert response.json == {
        "field1": "field1 value",
        "field2": "field2 value",
    }


def test_response_fails_validation_dict(caplog) -> None:
    class Response(BaseModel):
        field1: str
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    async def do_work() -> Union[dict, Response]:
        return {
            "field2": "field2 value",
        }

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 500, response.json
    assert "pydantic model error on api response serialization" in caplog.text
    assert "Response\nfield1\n  Field required [type=missing" in caplog.text


def test_response_non_model(caplog) -> None:
    class Response(BaseModel):
        field1: str
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    async def do_work() -> Union[str, Response]:
        return "boo"

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert response.text == "boo"


def test_async_view() -> None:
    class Response(BaseModel):
        field1: str
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    async def do_work() -> Response:
        return Response(
            field1="field1 value",
            field2="field2 value",
        )

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200, response.json
    assert response.json == {
        "field1": "field1 value",
        "field2": "field2 value",
    }


def test_fields_in_signature() -> None:
    class Response(BaseModel):
        field1: str
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    def do_work(fields: List[str]) -> Response:
        assert fields == ["a", "b", "c.d"]

        return Response(
            field1="field1 value",
            field2="field2 value",
        )

    client = app.test_client()
    response = client.get("/?fields=a,b,c.d")

    assert response.status_code == 200, response.json
    assert response.json == {
        "field1": "field1 value",
        "field2": "field2 value",
    }


def test_post_fields_in_signature() -> None:
    class Response(BaseModel):
        field1: str
        field2: str

    app = Flask("test_app")

    @app.post("/")
    @pydantic_api()
    def do_work(fields: List[str]) -> Response:
        assert fields == ["a", "b", "c.d"]

        return Response(
            field1="field1 value",
            field2="field2 value",
        )

    client = app.test_client()
    response = client.post("/", json={"fields": ["a", "b", "c.d"]})

    assert response.status_code == 200, response.json
    assert response.json == {
        "field1": "field1 value",
        "field2": "field2 value",
    }


def test_empty_fields_in_signature() -> None:
    class Response(BaseModel):
        field1: str
        field2: str

    app = Flask("test_app")

    @app.get("/")
    @pydantic_api()
    def do_work(fields: List[str]) -> Response:
        assert fields == []

        return Response(
            field1="field1 value",
            field2="field2 value",
        )

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200, response.json
    assert response.json == {
        "field1": "field1 value",
        "field2": "field2 value",
    }


def test_union_response_same_status_code() -> None:
    class ResponseA(BaseModel):
        field1: str

    class ResponseB(BaseModel):
        field2: str

    app = Flask("test_app")

    @app.get("/ret1")
    @pydantic_api()
    def do_work() -> Union[ResponseA, ResponseB]:
        return ResponseA(field1="val1")

    @app.get("/ret2")
    @pydantic_api()
    def do_work2() -> Union[ResponseA, ResponseB]:
        return ResponseB(field2="val2")

    client = app.test_client()
    response = client.get("/ret1")

    assert response.status_code == 200
    assert response.json

    assert response.json["field1"] == "val1"

    response = client.get("/ret2")

    assert response.status_code == 200
    assert response.json

    assert response.json["field2"] == "val2"


def test_union_response_different_status_code() -> None:
    class RequestA(BaseModel):
        switch: str

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
    def do_work(body: RequestA) -> Union[ResponseA, ResponseB]:
        if body.switch == "A":
            return ResponseA(field1="val1")
        else:
            return ResponseB(field2="val2")

    client = app.test_client()
    response = client.get("/?switch=A")

    assert response.status_code == 200
    assert response.json

    assert response.json["field1"] == "val1"

    response = client.get("/?switch=B")

    assert response.status_code == 202
    assert response.json

    assert response.json["field2"] == "val2"
