#!/usr/bin/env bash

set -e
set -x

isort flask_pydantic_api tests
black flask_pydantic_api tests
flake8 flask_pydantic_api tests
mypy -p flask_pydantic_api -p tests
