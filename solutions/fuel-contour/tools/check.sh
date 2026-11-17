#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-.venv/bin/python}"
"$PYTHON" tools/verify_vendor.py
"$PYTHON" -m pytest -q
# Intentionally strict: the known upstream error is NOT silenced or relabelled success.
"$PYTHON" vendor/test_oil/tools/validate_reference_repo.py
