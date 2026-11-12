"""Command-line interface for pdf2video."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
from typing import Optional

from . import __version__
from .batch import process_batch
from .config import ConfigError, load_config
from .ffmpeg_check import FFmpegNotFoundError, find_ffmpeg

logger = logging.getLogger("pdf2video")


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None) -> None:
    """Configure console and optional file logging handlers."""
    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers to prevent duplicates
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        try:
            log_path = Path(log_file).resolve()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            logger.warning("Could not initialize log file '%s': %s", log_file, e)


def create_parser() -> argparse.ArgumentParser:
    """Construct argument parser for pdf2video CLI."""
    parser = argparse.ArgumentParser(
        prog="pdf2video",
        description="Convert PDF files into sharp, lightweight MP4 videos with background music.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit.",
    )

    parser.add_argument(
        "-c", "--config",
        dest="config_path",
        type=Path,
        default=None,
        help="Path to YAML configuration file (defaults to config.yaml in CWD if present).",
    )

    parser.add_argument(
        "-i", "--input",
        dest="input_folder",
        type=Path,
        default=None,
        help="Input PDF file or folder containing PDF files.",
    )

    parser.add_argument(
        "-o", "--output",
        dest="output_folder",
        type=Path,
        default=None,
        help="Output folder where MP4 videos will be saved.",
    )

    parser.add_argument(
        "-s", "--seconds-per-page",
        dest="seconds_per_page",
        type=float,
        default=None,
        help="Duration in seconds each PDF page frame is shown.",
    )

    parser.add_argument(
        "-m", "--music",
        dest="music_file",
        type=Path,
        default=None,
        help="Path to background audio file (MP3, WAV, AAC, M4A, FLAC, OGG).",
    )

    parser.add_argument(
        "--volume",
        dest="music_volume",
        type=float,
        default=None,
        help="Background music volume factor (0.0 to 1.0, default: 0.15).",
    )

    parser.add_argument(
        "--fade-out",
        dest="music_fade_out_seconds",
        type=float,
        default=None,
        help="Audio fade-out duration in seconds at end of video.",
    )

    parser.add_argument(
        "-w", "--width",
        dest="render_width",
        type=int,
        default=None,
        help="Target page rendering width in pixels (e.g. 1920).",
    )

    parser.add_argument(
        "--bg-color",
        dest="background_color",
        type=str,
        default=None,
        help="Canvas padding background color (e.g. 'white' or '#FFFFFF').",
    )

    parser.add_argument(
        "--fps",
        dest="fps",
        type=int,
        default=None,
        help="Video frame rate in fps (default: 2).",
    )

    parser.add_argument(
        "--crf",
        dest="crf",
        type=int,
        default=None,
        help="H.264 Constant Rate Factor (0-51, default: 23).",
    )

    parser.add_argument(
        "--preset",
        dest="preset",
        type=str,
        default=None,
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
        help="H.264 compression speed preset.",
    )

    parser.add_argument(
        "--bitrate",
        dest="audio_bitrate",
        type=str,
        default=None,
        help="Audio bitrate for AAC stream (e.g. '64k', '128k').",
    )

    parser.add_argument(
        "--channels",
        dest="audio_channels",
        type=str,
        default=None,
        choices=["stereo", "mono"],
        help="Audio channel configuration.",
    )

    parser.add_argument(
        "--workers",
        dest="workers",
        type=int,
        default=None,
        help="Number of parallel worker processes (defaults to half of CPU cores).",
    )

    parser.add_argument(
        "-r", "--recursive",
        dest="recursive",
        action="store_true",
        default=None,
        help="Scan input folder recursively for PDF files.",
    )

    parser.add_argument(
        "--overwrite",
        dest="overwrite",
        action="store_true",
        default=None,
        help="Force overwrite of existing output MP4 files.",
    )

    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="List files that would be converted without producing videos.",
    )

    parser.add_argument(
        "--compact", "--ultra-compact",
        dest="compact",
        action="store_true",
        default=False,
        help="Apply maximum compression profile (960px width, CRF 28, veryslow preset, 32k mono audio).",
    )

    parser.add_argument(
        "--log-file",
        dest="log_file",
        type=Path,
        default=None,
        help="Path to an optional log file.",
    )

    parser.add_argument(
        "--ffmpeg-path",
        dest="ffmpeg_path",
        type=Path,
        default=None,
        help="Custom path to ffmpeg executable.",
    )

    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Enable detailed debug log output.",
    )

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point for pdf2video."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # Build overrides dict with only explicitly provided CLI flags
    overrides: dict[str, any] = {}
    cli_fields = [
        "input_folder",
        "output_folder",
        "seconds_per_page",
        "music_file",
        "music_volume",
        "music_fade_out_seconds",
        "render_width",
        "background_color",
        "fps",
        "crf",
        "preset",
        "audio_bitrate",
        "audio_channels",
        "workers",
        "recursive",
        "overwrite",
        "log_file",
        "ffmpeg_path",
    ]

    # If compact mode profile requested, set optimal compression defaults
    if getattr(args, "compact", False):
        compact_profile: dict[str, any] = {
            "render_width": 960,
            "crf": 28,
            "preset": "veryslow",
            "audio_bitrate": "32k",
            "audio_channels": "mono",
        }
        for k, v in compact_profile.items():
            if getattr(args, k, None) is None:
                overrides[k] = v

    for field in cli_fields:
        val = getattr(args, field, None)
        if val is not None:
            overrides[field] = val

    try:
        config = load_config(config_path=args.config_path, overrides=overrides)
    except ConfigError as err:
        sys.stderr.write(f"\nConfiguration Error: {err}\n\n")
        return 1

    # Initialize logging
    setup_logging(verbose=args.verbose, log_file=config.log_file)

    # Check at startup that FFmpeg is installed
    try:
        find_ffmpeg(config.ffmpeg_path)
    except FFmpegNotFoundError as err:
        sys.stderr.write(f"\n{err}\n\n")
        return 1

    # Execute batch
    try:
        exit_code, _ = process_batch(config=config, dry_run=args.dry_run)
        return exit_code
    except FFmpegNotFoundError as err:
        sys.stderr.write(f"\n{err}\n\n")
        return 1
    except KeyboardInterrupt:
        logger.warning("\nProcess interrupted by user. Exiting...")
        return 130
    except Exception as err:
        logger.exception("Fatal unexpected error: %s", err)
        return 1


if __name__ == "__main__":
    sys.exit(main())
