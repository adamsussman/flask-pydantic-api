# This is meant mainly as an example.  You probably want to customize the openapi
# schema object more as well as the doc viewer setup

import pkg_resources
from flask import Blueprint, Response, make_response, render_template_string

from .openapi import get_openapi_schema

blueprint = Blueprint("apidocs", __name__)


@blueprint.get("/openapi.json")
def get_openapi_spec() -> Response:
    spec = get_openapi_schema()

    return make_response(
        (
            spec.model_dump_json(by_alias=True, exclude_none=True, indent=2),
            {"content-type": "application/json"},
        )
    )


@blueprint.get("/")
def get_apidocs() -> str:
    viewer_template = pkg_resources.resource_string(
        "flask_pydantic_api", "templates/rapidoc.html"
    )
    return render_template_string(viewer_template.decode("utf8"))
