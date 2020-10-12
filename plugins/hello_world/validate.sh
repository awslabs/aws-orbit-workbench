#!/usr/bin/env bash
set -ex

isort --line-length 120 .
black --line-length 120 --target-version py36 .
mypy --python-version 3.6 --strict --ignore-missing-imports .
flake8 --max-line-length 120 .
