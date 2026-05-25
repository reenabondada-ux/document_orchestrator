#!/bin/bash
# Run tests with proper PYTHONPATH configuration

set -euo pipefail

cd "$(dirname "$0")"
source .venv/bin/activate

export PYTHONPATH="./src:${PYTHONPATH:-}"

# Run pytest with all arguments passed to this script
exec pytest "$@"
