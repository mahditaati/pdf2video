#!/usr/bin/env bash
# ==============================================================================
# Git Commits & GitHub Repository Setup Script for pdf2video
# ==============================================================================
set -e

echo "=== 1. Checking Git Status ==="
git status --short

echo ""
echo "=== 2. Making Logical Conventional Commits ==="

# Commit 1: Project configuration, dependencies, and gitignore
if git status --porcelain | grep -qE "(\.gitignore|pyproject\.toml|requirements\.txt)"; then
    git add .gitignore pyproject.toml requirements.txt
    git commit -m "chore: configure project dependencies and ignore patterns" || true
fi

# Commit 2: Config module and config.yaml
if git status --porcelain | grep -qE "(src/pdf2video/config\.py|config\.yaml)"; then
    git add src/pdf2video/config.py config.yaml
    git commit -m "feat(config): add configuration schema, YAML loader, and validation" || true
fi

# Commit 3: PDF rendering and letterboxing
if git status --porcelain | grep -qE "src/pdf2video/renderer\.py"; then
    git add src/pdf2video/renderer.py
    git commit -m "feat(renderer): add PDF rasterization with aspect-ratio letterboxing" || true
fi

# Commit 4: Audio handling and synchronization
if git status --porcelain | grep -qE "src/pdf2video/audio\.py"; then
    git add src/pdf2video/audio.py
    git commit -m "feat(audio): add background audio detection, duration probe, and sync filters" || true
fi

# Commit 5: FFmpeg video encoding engine
if git status --porcelain | grep -qE "(src/pdf2video/encoder\.py|src/pdf2video/ffmpeg_check\.py)"; then
    git add src/pdf2video/encoder.py src/pdf2video/ffmpeg_check.py
    git commit -m "feat(encoder): add FFmpeg video encoding engine and atomic output writer" || true
fi

# Commit 6: Batch processing and multiprocessing
if git status --porcelain | grep -qE "src/pdf2video/batch\.py"; then
    git add src/pdf2video/batch.py
    git commit -m "feat(batch): add multi-process batch converter with skip logic and error containment" || true
fi

# Commit 7: CLI interface and package entry point
if git status --porcelain | grep -qE "(src/pdf2video/cli\.py|src/pdf2video/__init__\.py)"; then
    git add src/pdf2video/cli.py src/pdf2video/__init__.py
    git commit -m "feat(cli): add command-line interface with flag overrides and progress display" || true
fi

# Commit 8: Automated test suite
if git status --porcelain | grep -qE "tests/"; then
    git add tests/
    git commit -m "test: add comprehensive test suite for config, renderer, audio, and e2e conversion" || true
fi

# Commit 9: Documentation
if git status --porcelain | grep -qE "README\.md"; then
    git add README.md
    git commit -m "docs: add comprehensive README with quick start, CLI reference, and troubleshooting" || true
fi

echo ""
echo "=== Git Commit History ==="
git log --oneline -n 10

echo ""
echo "=== 3. GitHub CLI Check & Repository Publishing ==="
if ! command -v gh &> /dev/null; then
    echo ""
    echo "[!] GitHub CLI ('gh') is not installed on your system."
    echo "To install 'gh' on macOS using Homebrew, run:"
    echo "    brew install gh"
    echo ""
    echo "After installation, authenticate with your GitHub account:"
    echo "    gh auth login"
    echo ""
    echo "Then re-run this script to create the public repository and push:"
    echo "    ./setup_git_and_push.sh"
    exit 0
fi

if ! gh auth status &> /dev/null; then
    echo ""
    echo "[!] You are not currently logged in to GitHub via 'gh'."
    echo "Please authenticate by running:"
    echo "    gh auth login"
    echo ""
    echo "Then re-run this script:"
    echo "    ./setup_git_and_push.sh"
    exit 0
fi

echo "[+] Logged in to GitHub. Creating public repository 'pdf2video'..."
gh repo create pdf2video \
    --public \
    --source=. \
    --remote=origin \
    --push \
    --description "Production-quality CLI tool that converts PDF files into crisp, lightweight MP4 videos with background music."

echo "[+] Setting GitHub repository topics..."
gh repo edit pdf2video --add-topic "pdf,video,converter,ffmpeg,pymupdf,slides,presentation,mp4,cli"

echo ""
echo "=== Repository successfully published to GitHub! ==="
gh repo view --web || true
