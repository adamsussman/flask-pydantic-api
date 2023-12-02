# This is meant mainly as an example.  You probably want to customize the openapi
# schema object more as well as the doc viewer setup

from typing import Any, Dict

import pkg_resources
from flask import Blueprint, render_template_string

from .openapi import get_openapi_schema

blueprint = Blueprint("apidocs", __name__)


@blueprint.get("/openapi.json")
def get_openapi_spec() -> Dict[str, Any]:
    return get_openapi_schema()


@blueprint.get("/")
def get_apidocs() -> str:
    viewer_template = pkg_resources.resource_string(
        "flask_pydantic_api", "templates/rapidoc.html"
    )
    return render_template_string(viewer_template.decode("utf8"))
