"""FFmpeg discovery and verification module."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)


class FFmpegNotFoundError(RuntimeError):
    """Raised when FFmpeg executable cannot be located or executed."""
    pass


def find_ffmpeg(custom_path: Optional[str | Path] = None) -> Path:
    """Locate the FFmpeg executable across custom path, PATH, and virtualenv.

    Args:
        custom_path: Optional user-specified path to the ffmpeg executable.

    Returns:
        Path object pointing to the verified ffmpeg binary.

    Raises:
        FFmpegNotFoundError: If FFmpeg cannot be found or is not executable.
    """
    candidates: list[Path] = []

    # 1. Custom user-specified path
    if custom_path:
        candidates.append(Path(custom_path).expanduser().resolve())

    # 2. PATH resolution
    path_bin = shutil.which("ffmpeg")
    if path_bin:
        candidates.append(Path(path_bin).resolve())

    # 3. Virtual environment directory (sys.prefix)
    venv_bin_dir = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    venv_ffmpeg = venv_bin_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    candidates.append(venv_ffmpeg)

    # 4. imageio_ffmpeg bundled binary if installed
    try:
        import imageio_ffmpeg  # type: ignore

        img_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if img_exe:
            candidates.append(Path(img_exe).resolve())
    except Exception:
        pass

    # 5. Standard operating system directories
    standard_paths = [
        Path("/opt/homebrew/bin/ffmpeg"),
        Path("/usr/local/bin/ffmpeg"),
        Path("/usr/bin/ffmpeg"),
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "FFmpeg" / "bin" / "ffmpeg.exe",
        Path("C:\\ffmpeg\\bin\\ffmpeg.exe"),
    ]
    candidates.extend(standard_paths)

    # Check each candidate
    for candidate in candidates:
        if candidate.is_file() and os.access(str(candidate), os.X_OK):
            try:
                result = subprocess.run(
                    [str(candidate), "-version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0:
                    logger.debug("Located FFmpeg at: %s", candidate)
                    return candidate
            except Exception as e:
                logger.debug("Failed checking candidate %s: %s", candidate, e)

    # If none succeeded, formulate a friendly error message
    error_msg = (
        "FFmpeg is not installed or could not be found on your system!\n\n"
        "pdf2video requires FFmpeg to encode videos and mix audio tracks.\n"
        "Please install FFmpeg using one of the following methods:\n"
        "  - macOS (Homebrew):   brew install ffmpeg\n"
        "  - Ubuntu / Debian:    sudo apt update && sudo apt install ffmpeg\n"
        "  - Arch Linux:         sudo pacman -S ffmpeg\n"
        "  - Windows (winget):   winget install Gyan.FFmpeg\n"
        "  - Or download from:   https://ffmpeg.org/download.html\n\n"
        "If FFmpeg is installed in a non-standard location, you can set 'ffmpeg_path' in\n"
        "config.yaml or pass '--ffmpeg-path /path/to/ffmpeg'."
    )
    raise FFmpegNotFoundError(error_msg)
