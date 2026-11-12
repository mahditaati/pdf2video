"""Video encoding module executing FFmpeg via subprocess."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
from typing import Optional
import uuid

from .audio import build_audio_filter, calculate_fade_out

logger = logging.getLogger(__name__)


class EncodeError(Exception):
    """Raised when FFmpeg encoding process fails."""
    pass


def encode_video(
    ffmpeg_exe: Path,
    frames_dir: Path,
    num_pages: int,
    seconds_per_page: float,
    output_file: Path,
    fps: int = 2,
    crf: int = 23,
    preset: str = "slow",
    audio_file: Optional[Path] = None,
    audio_volume: float = 0.15,
    audio_fade_out_seconds: float = 2.0,
    audio_bitrate: str = "64k",
    audio_channels: str = "stereo",
) -> Path:
    """Encode rendered page frames and background audio into an MP4 video.

    Writes to a temporary file first and atomically renames to the final output
    file on success, ensuring interrupted runs never leave partial videos.

    Args:
        ffmpeg_exe: Verified path to the FFmpeg binary.
        frames_dir: Directory containing page_00000.png, page_00001.png, etc.
        num_pages: Total count of pages in the document.
        seconds_per_page: Duration each page is displayed.
        output_file: Destination path for the completed MP4 video.
        fps: Output video frame rate (default 2).
        crf: Constant Rate Factor (default 23).
        preset: x264 preset (default 'slow').
        audio_file: Optional path to background music file.
        audio_volume: Music volume factor (default 0.15).
        audio_fade_out_seconds: Fade-out duration at video end (default 2.0).
        audio_bitrate: AAC bitrate (default '64k').
        audio_channels: 'stereo' or 'mono'.

    Returns:
        Path to the completed output video.

    Raises:
        EncodeError: If FFmpeg fails to encode or produce the video.
    """
    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write target
    random_token = uuid.uuid4().hex[:8]
    temp_output = output_file.with_name(
        f".tmp.{os.getpid()}.{random_token}.{output_file.name}"
    )

    total_duration = float(num_pages) * float(seconds_per_page)
    channels_count = 1 if str(audio_channels).lower() in ("mono", "1") else 2

    # If seconds_per_page is faster than 1/fps, adjust effective fps so no page frames are dropped
    min_required_fps = int(1.0 / float(seconds_per_page)) + (1 if (1.0 / float(seconds_per_page)) % 1 > 1e-6 else 0)
    effective_fps = max(fps, min_required_fps)
    if effective_fps != fps:
        logger.debug(
            "Increased output fps from %d to %d to preserve all pages with fast duration (%.2fs/page)",
            fps,
            effective_fps,
            seconds_per_page,
        )

    # Verify input frames template
    frame_pattern = str(frames_dir / "page_%05d.png")

    cmd: list[str] = [
        str(ffmpeg_exe),
        "-y",
        "-framerate",
        str(1.0 / float(seconds_per_page)),
        "-i",
        frame_pattern,
    ]

    has_audio = audio_file is not None and Path(audio_file).is_file()
    if has_audio:
        cmd.extend([
            "-stream_loop",
            "-1",
            "-i",
            str(Path(audio_file).resolve()),
        ])

        filter_str = build_audio_filter(
            volume=audio_volume,
            total_duration=total_duration,
            fade_out_seconds=audio_fade_out_seconds,
            input_label="1:a",
            output_label="a",
        )

        audio_args = [
            "-c:a",
            "aac",
            "-b:a",
            str(audio_bitrate),
            "-ac",
            str(channels_count),
        ]
        # Optimize sample rate for mono or low bitrate to cut audio payload
        if channels_count == 1:
            audio_args.extend(["-ar", "32000"])

        cmd.extend([
            "-filter_complex",
            filter_str,
            "-map",
            "0:v",
            "-map",
            "[a]",
            *audio_args,
        ])
    else:
        cmd.extend([
            "-map",
            "0:v",
        ])

    # High-efficiency x264 parameters for static slide / document content
    # Long GOP prevents wasteful I-frame bursts on static frames
    keyint = max(50, effective_fps * 10)
    x264_opts = (
        f"keyint={keyint}:min-keyint={effective_fps}:scenecut=0:"
        "bframes=8:b-adapt=2:ref=4:aq-mode=2"
    )

    cmd.extend([
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        str(crf),
        "-preset",
        str(preset),
        "-tune",
        "stillimage",
        "-x264-params",
        x264_opts,
        "-r",
        str(effective_fps),
        "-t",
        f"{total_duration:.4f}".rstrip("0").rstrip("."),
        "-movflags",
        "+faststart",
        str(temp_output),
    ])

    logger.debug("Executing FFmpeg command: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if proc.returncode != 0:
            err_snippet = proc.stderr[-1000:] if proc.stderr else "Unknown error"
            raise EncodeError(
                f"FFmpeg failed with exit code {proc.returncode}:\n{err_snippet}"
            )

        if not temp_output.is_file() or temp_output.stat().st_size == 0:
            raise EncodeError("FFmpeg produced an empty or missing output file.")

        # Atomic replacement of destination file
        temp_output.replace(output_file)
        logger.info("Successfully encoded video: %s", output_file)
        return output_file

    except Exception:
        if temp_output.exists():
            try:
                temp_output.unlink()
            except OSError:
                pass
        raise
