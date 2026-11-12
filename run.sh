#!/usr/bin/env bash
# ==============================================================================
# pdf2video - Easy runner script
# Usage:
#   ./run.sh                  -> Convert all PDFs in input/ to output/
#   ./run.sh document.pdf     -> Convert a single PDF file
#   ./run.sh dry              -> Preview what will be converted
#   ./run.sh test             -> Run test suite
#   ./run.sh [any cli flags]  -> Pass custom flags (e.g. ./run.sh -s 2 --overwrite)
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Locate Python with dependencies
if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

export PYTHONPATH="src:${PYTHONPATH:-}"

# 2. Shortcut commands
if [ "$1" = "test" ]; then
    echo "==> Running test suite..."
    exec "$PYTHON" -m unittest discover tests
fi

if [ "$1" = "dry" ] || [ "$1" = "preview" ]; then
    shift
    exec "$PYTHON" -m pdf2video.cli --dry-run "$@"
fi

if [ "$1" = "overwrite" ] || [ "$1" = "force" ]; then
    shift
    exec "$PYTHON" -m pdf2video.cli --overwrite "$@"
fi

# 3. If first argument is an existing PDF file
if [ -n "$1" ] && [ -f "$1" ] && [[ "$1" == *.pdf ]]; then
    PDF_FILE="$1"
    shift
    exec "$PYTHON" -m pdf2video.cli -i "$PDF_FILE" "$@"
fi

# 4. Default execution
exec "$PYTHON" -m pdf2video.cli "$@"
