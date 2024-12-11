# This is meant mainly as an example.  You probably want to customize the openapi
# schema object more as well as the doc viewer setup

import os
from typing import Any, Dict

from flask import Blueprint, render_template_string

from .openapi import get_openapi_schema

blueprint = Blueprint("apidocs", __name__)


@blueprint.get("/openapi.json")
def get_openapi_spec() -> Dict[str, Any]:
    return get_openapi_schema()


@blueprint.get("/")
def get_apidocs() -> str:
    viewer_template = os.path.join(os.path.dirname(__file__), "templates/rapidoc.html")
    return render_template_string(viewer_template)
