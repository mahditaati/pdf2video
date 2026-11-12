"""Audio processing, detection, and filter construction."""

from __future__ import annotations

import logging
from pathlib import Path
import re
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


def auto_detect_music_file(
    explicit_path: Optional[Path] = None,
    search_dirs: Optional[list[Path]] = None,
) -> Optional[Path]:
    """Find a background music file, checking explicit path, music/, or project root.

    Args:
        explicit_path: User-configured path to check first.
        search_dirs: List of directory paths to scan if explicit path is not set.

    Returns:
        Path to the resolved audio file, or None if none found.
    """
    if explicit_path is not None:
        p = explicit_path.expanduser().resolve()
        if p.is_file():
            return p

    if search_dirs is None:
        search_dirs = [Path("music"), Path(".")]

    for directory in search_dirs:
        dir_path = directory.resolve()
        if not dir_path.is_dir():
            continue

        try:
            entries = sorted(dir_path.iterdir())
        except OSError:
            continue

        for entry in entries:
            if entry.is_file() and entry.suffix.lower() in AUDIO_EXTENSIONS:
                logger.debug("Auto-detected background music file: %s", entry)
                return entry.resolve()

    return None


def probe_media_duration(ffmpeg_exe: Path, media_path: Path) -> Optional[float]:
    """Inspect media file with FFmpeg and return its duration in seconds.

    Args:
        ffmpeg_exe: Path to FFmpeg executable.
        media_path: Path to audio or video file.

    Returns:
        Duration in seconds as a float, or None if it cannot be determined.
    """
    cmd = [str(ffmpeg_exe), "-i", str(media_path)]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as e:
        logger.warning("Error running ffmpeg probe on %s: %s", media_path, e)
        return None

    # ffmpeg writes file inspection to stderr
    output = proc.stderr
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    if match:
        hours, minutes, seconds = match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        return duration

    return None


def calculate_fade_out(
    total_duration: float,
    requested_fade_seconds: float = 2.0,
) -> tuple[float, float]:
    """Calculate exact fade-out start and duration.

    Args:
        total_duration: Total video length in seconds.
        requested_fade_seconds: Desired fade-out duration.

    Returns:
        (fade_start, fade_duration) in seconds.
    """
    total_duration = max(0.0, float(total_duration))
    requested_fade_seconds = max(0.0, float(requested_fade_seconds))
    fade_duration = min(requested_fade_seconds, total_duration)
    fade_start = max(0.0, total_duration - fade_duration)
    return fade_start, fade_duration


def build_audio_filter(
    volume: float,
    total_duration: float,
    fade_out_seconds: float = 2.0,
    input_label: str = "",
    output_label: str = "",
) -> str:
    """Build FFmpeg audio filter string for volume scaling and ending fade-out.

    Args:
        volume: Volume scaling factor (e.g. 0.15).
        total_duration: Total video duration in seconds.
        fade_out_seconds: Fade duration in seconds.
        input_label: Optional input stream pad label (e.g. "1:a").
        output_label: Optional output stream pad label (e.g. "a").

    Returns:
        FFmpeg audio filter string.
    """
    fade_start, fade_dur = calculate_fade_out(total_duration, fade_out_seconds)
    vol_clamped = max(0.0, float(volume))
    filters = [f"volume={vol_clamped:.3f}"]
    if fade_dur > 0:
        filters.append(f"afade=t=out:st={fade_start:.3f}:d={fade_dur:.3f}")

    chain = ",".join(filters)
    in_prefix = f"[{input_label}]" if input_label else ""
    out_suffix = f"[{output_label}]" if output_label else ""
    return f"{in_prefix}{chain}{out_suffix}"
