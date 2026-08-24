#!/usr/bin/env bash
# One command that takes this repo from clone to running tests.
#
# If a human needs four commands and some tribal knowledge to boot the project,
# an agent has no chance. This file is the contract that says otherwise, and the
# harness runs it before any agent touches the code.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt

echo "ready. tests:  .venv/bin/python -m pytest -q"
