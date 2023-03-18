#!/usr/bin/env bash

set -e
set -x

pip install -q build
python -m build
