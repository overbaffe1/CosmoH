#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m fuel.cli suite --output results
.venv/bin/python tools/report.py
bash tools/check.sh
