#!/bin/bash
# General-purpose Python wrapper with correct environment and PYTHONPATH
#
# Usage examples:
#   ./run.sh examples/run_demo.py                         # Run a script
#   ./run.sh examples/run_demo.py --verbose               # Run with arguments
#   ./run.sh -m pytest tests/                             # Run a module
#   ./run.sh -c "print('Hello')"                          # Execute code string
#   ./run.sh                                              # Interactive Python REPL
#
# This script:
# - Activates the virtual environment
# - Sets PYTHONPATH to include src/ for proper imports
# - Passes all arguments to Python

set -euo pipefail

cd "$(dirname "$0")"
source .venv/bin/activate

export PYTHONPATH="./src:${PYTHONPATH:-}"

exec python "$@"
