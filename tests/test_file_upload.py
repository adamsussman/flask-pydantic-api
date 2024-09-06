import io
from typing import Union

from flask import Flask
from pydantic import BaseModel
from werkzeug.datastructures import FileStorage

from flask_pydantic_api import UploadedFile, pydantic_api


def test_simple_file_upload() -> None:
    class Request(BaseModel):
        some_file: UploadedFile
        other_var: str

    app = Flask("test_app")

    @app.post("/")
    @pydantic_api()
    def do_work(body: Request) -> str:
        assert body.other_var == "some value"
        return body.some_file.read().decode("ascii")

    file_data = b"a;ild[oisadfcnklasdfoi2390adnkjladnlakdass"

    client = app.test_client()
    response = client.post(
        "/",
        content_type="multipart/form-data",
        data={
            "some_file": FileStorage(
                stream=io.BytesIO(file_data),
                filename="whatever",
            ),
            "other_var": "some value",
        },
    )

    assert response.status_code == 200
    assert response.data == file_data


def test_file_upload_wrong_content_type() -> None:
    class Request(BaseModel):
        some_file: UploadedFile

    app = Flask("test_app")

    @app.post("/")
    @pydantic_api()
    def do_work(body: Request) -> str:
        return ""

    client = app.test_client()
    response = client.post("/", json={"some_file": "boo!"})

    assert response.status_code == 415
    assert b"multipart/form-data expected" in response.data


def test_file_field_missing() -> None:
    class Request(BaseModel):
        some_file: UploadedFile
        blah: str

    app = Flask("test_app")
    app.config["FLASK_PYDANTIC_API_RENDER_ERRORS"] = True

    @app.post("/")
    @pydantic_api()
    def do_work(body: Request) -> str:
        return ""

    client = app.test_client()
    response = client.post(
        "/",
        content_type="multipart/form-data",
        data={
            "blah": "whatever",
        },
    )

    assert response.status_code == 400
    assert response.json

    assert len(response.json["errors"]) == 1
    assert response.json["errors"][0]["loc"] == ["some_file"]
    assert response.json["errors"][0]["msg"] == "Field required"
    assert response.json["errors"][0]["type"] == "missing"


def test_file_upload_wrong_field_type() -> None:
    class Request(BaseModel):
        some_file: UploadedFile

    app = Flask("test_app")
    app.config["FLASK_PYDANTIC_API_RENDER_ERRORS"] = True

    @app.post("/")
    @pydantic_api()
    def do_work(body: Request) -> str:
        return ""

    client = app.test_client()
    response = client.post(
        "/", content_type="multipart/form-data", data={"some_file": "boo!"}
    )

    assert response.status_code == 400
    assert response.json

    assert len(response.json["errors"]) == 1
    assert response.json["errors"][0]["loc"] == ["some_file"]
    assert response.json["errors"][0]["msg"] == "file required"
    assert response.json["errors"][0]["type"] == "file_type"


def test_multi_file_upload() -> None:
    class Request(BaseModel):
        file1: UploadedFile
        file2: UploadedFile
        other_var: str

    class Response(BaseModel):
        file1: str
        file2: str
        other_var: str

    app = Flask("test_app")

    @app.post("/")
    @pydantic_api()
    def do_work(body: Request) -> Response:
        return Response(
            file1=body.file1.read().decode("ascii"),
            file2=body.file2.read().decode("ascii"),
            other_var=body.other_var,
        )

    file_data1 = b"a;ild[oisadfcnklasdfoi2390adnkjladnlakdass"
    file_data2 = b"m908s9dvcjknsk;jsd890"

    client = app.test_client()
    response = client.post(
        "/",
        content_type="multipart/form-data",
        data={
            "file1": FileStorage(
                stream=io.BytesIO(file_data1),
                filename="whatever",
            ),
            "file2": FileStorage(
                stream=io.BytesIO(file_data2),
                filename="whatever",
            ),
            "other_var": "some value",
        },
    )

    assert response.status_code == 200
    assert response.json

    assert response.json == {
        "file1": file_data1.decode("ascii"),
        "file2": file_data2.decode("ascii"),
        "other_var": "some value",
    }


def test_union_model_and_uploader() -> None:
    class FileRequest(BaseModel):
        file1: UploadedFile
        other_var: str

    class OtherRequest(BaseModel):
        val1: str

    app = Flask("test_app")

    @app.post("/")
    @pydantic_api()
    def do_work(body: Union[FileRequest, OtherRequest]) -> dict:
        if isinstance(body, FileRequest):
            return {"body": "FileRequest"}

        if isinstance(body, OtherRequest):
            return {"body": "OtherRequest"}

        return {"body": "unknown"}

    client = app.test_client()

    response = client.post(
        "/",
        content_type="multipart/form-data",
        data={
            "file1": FileStorage(
                stream=io.BytesIO(b"abc123"),
                filename="whatever",
            ),
            "other_var": "foo",
        },
    )
    assert response.status_code == 200
    assert response.json
    assert response.json["body"] == "FileRequest"

    response = client.post("/", json={"val1": "foo"})
    assert response.status_code == 200
    assert response.json
    assert response.json["body"] == "OtherRequest"


def test_union_model_and_uploader_validation() -> None:
    class FileRequest(BaseModel):
        file1: UploadedFile
        other_var: str

    class OtherRequest(BaseModel):
        val1: str

    app = Flask("test_app")
    app.config["FLASK_PYDANTIC_API_RENDER_ERRORS"] = True

    @app.post("/")
    @pydantic_api()
    def do_work(body: Union[FileRequest, OtherRequest]) -> dict:
        if isinstance(body, FileRequest):
            return {"body": "FileRequest"}

        if isinstance(body, OtherRequest):
            return {"body": "OtherRequest"}

        return {"body": "unknown"}

    client = app.test_client()

    response = client.post(
        "/", content_type="multipart/form-data", data={"other_var": "foo"}
    )
    assert response.status_code == 400
    assert response.json

    # pytest error urls change by version
    errors = response.json["errors"]
    for err in errors:
        assert "missing" in err.pop("url", "")

    assert errors[0] == {
        "input": {
            "other_var": "foo",
        },
        "loc": [
            "file1",
        ],
        "msg": "Field required",
        "type": "missing",
    }

    response = client.post("/", json={})
    assert response.status_code == 400
    assert response.json

    # pytest error urls change by version
    errors = response.json["errors"]
    for err in errors:
        assert "missing" in err.pop("url", "")

    assert errors[0] == {
        "input": {},
        "loc": [
            "val1",
        ],
        "msg": "Field required",
        "type": "missing",
    }
