"""Configuration management and validation for pdf2video."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from typing import Any, Optional
import yaml
from PIL import ImageColor

logger = logging.getLogger(__name__)

VALID_PRESETS = {
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
}

VALID_CHANNELS = {"mono": 1, "stereo": 2, "1": 1, "2": 2, 1: 1, 2: 2}


class ConfigError(ValueError):
    """Raised when configuration values are invalid or missing required files."""
    pass


@dataclass
class AppConfig:
    """Strongly typed application configuration."""

    input_folder: Path = field(default_factory=lambda: Path("input"))
    output_folder: Path = field(default_factory=lambda: Path("output"))
    seconds_per_page: float = 1.0
    music_file: Optional[Path] = None
    music_volume: float = 0.15
    music_fade_out_seconds: float = 2.0
    render_width: int = 1920
    background_color: str = "#FFFFFF"
    fps: int = 2
    crf: int = 23
    preset: str = "slow"
    audio_bitrate: str = "64k"
    audio_channels: str = "stereo"
    workers: Optional[int] = None
    recursive: bool = False
    overwrite: bool = False
    log_file: Optional[Path] = None
    ffmpeg_path: Optional[Path] = None

    def validate(self, base_dir: Optional[Path] = None) -> None:
        """Validate all configuration attributes and raise descriptive errors.

        Args:
            base_dir: Directory against which relative paths are resolved.
        """
        if self.seconds_per_page <= 0:
            raise ConfigError(
                f"Invalid 'seconds_per_page' ({self.seconds_per_page}). Must be greater than 0."
            )

        if self.music_volume < 0.0:
            raise ConfigError(
                f"Invalid 'music_volume' ({self.music_volume}). Cannot be negative."
            )

        if self.music_fade_out_seconds < 0.0:
            raise ConfigError(
                f"Invalid 'music_fade_out_seconds' ({self.music_fade_out_seconds}). Cannot be negative."
            )

        if self.render_width <= 0:
            raise ConfigError(
                f"Invalid 'render_width' ({self.render_width}). Must be a positive integer."
            )

        if self.fps <= 0:
            raise ConfigError(f"Invalid 'fps' ({self.fps}). Must be greater than 0.")

        if not (0 <= self.crf <= 51):
            raise ConfigError(
                f"Invalid 'crf' ({self.crf}). Must be an integer between 0 (lossless) and 51 (worst)."
            )

        preset_lower = self.preset.lower().strip()
        if preset_lower not in VALID_PRESETS:
            raise ConfigError(
                f"Invalid 'preset' '{self.preset}'. Must be one of: {', '.join(sorted(VALID_PRESETS))}."
            )
        self.preset = preset_lower

        if self.audio_channels not in VALID_CHANNELS:
            raise ConfigError(
                f"Invalid 'audio_channels' '{self.audio_channels}'. Must be 'mono' or 'stereo'."
            )

        if self.workers is not None and self.workers < 1:
            raise ConfigError(
                f"Invalid 'workers' ({self.workers}). Must be at least 1 or null for auto."
            )

        # Validate audio bitrate
        import re
        if not re.match(r"^\d+[kKmM]?$", str(self.audio_bitrate).strip()):
            raise ConfigError(
                f"Invalid 'audio_bitrate' '{self.audio_bitrate}'. "
                f"Expected format like '64k', '128k', or '64000'."
            )

        # Validate background color
        try:
            ImageColor.getrgb(self.background_color)
        except ValueError as err:
            raise ConfigError(
                f"Invalid 'background_color' '{self.background_color}'. "
                f"Must be a recognizable color name or hex code (e.g. '#FFFFFF')."
            ) from err

        # Validate explicit input PDF file if specified
        if self.input_folder.suffix.lower() == ".pdf":
            resolved_input = self.input_folder
            if not resolved_input.is_absolute() and base_dir is not None:
                candidate = (base_dir / resolved_input).resolve()
                if candidate.exists():
                    resolved_input = candidate
                else:
                    resolved_input = resolved_input.resolve()
            else:
                resolved_input = resolved_input.resolve()

            if not resolved_input.is_file():
                raise ConfigError(
                    f"Specified input PDF file does not exist: {self.input_folder} "
                    f"(resolved: {resolved_input})"
                )
            self.input_folder = resolved_input

        # Validate music file if explicitly set
        if self.music_file is not None:
            resolved_music = self.music_file
            if not resolved_music.is_absolute() and base_dir is not None:
                candidate = (base_dir / resolved_music).resolve()
                if candidate.exists():
                    resolved_music = candidate
                else:
                    resolved_music = resolved_music.resolve()
            else:
                resolved_music = resolved_music.resolve()

            if not resolved_music.is_file():
                raise ConfigError(
                    f"Configured music file does not exist: {self.music_file} "
                    f"(resolved: {resolved_music})"
                )
            self.music_file = resolved_music


def load_config(
    config_path: Optional[str | Path] = None,
    overrides: Optional[dict[str, Any]] = None,
) -> AppConfig:
    """Load configuration from YAML file and apply CLI overrides.

    Args:
        config_path: Path to YAML config file. If None, checks 'config.yaml' at CWD.
        overrides: Optional dictionary of CLI argument overrides.

    Returns:
        Validated AppConfig instance.
    """
    raw_data: dict[str, Any] = {}
    config_file: Optional[Path] = None

    if config_path is not None:
        candidate = Path(config_path).expanduser().resolve()
        if not candidate.is_file():
            raise ConfigError(f"Specified config file does not exist: {config_path}")
        config_file = candidate
    else:
        candidate = Path("config.yaml").resolve()
        if candidate.is_file():
            config_file = candidate

    if config_file is not None:
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if isinstance(content, dict):
                    raw_data = content
                elif content is not None:
                    raise ConfigError(
                        f"Config file '{config_file}' is invalid: root must be a YAML mapping/dictionary."
                    )
        except yaml.YAMLError as e:
            raise ConfigError(f"Error parsing YAML config file '{config_file}': {e}") from e

    # Apply overrides from CLI
    if overrides:
        for k, v in overrides.items():
            if v is not None:
                raw_data[k] = v

    base_dir = config_file.parent if config_file else Path.cwd()

    def to_path(val: Any) -> Optional[Path]:
        if val is None or str(val).strip().lower() in ("", "none", "null"):
            return None
        return Path(val)

    def to_float(val: Any, field_name: str, default: float) -> float:
        if val is None or str(val).strip().lower() in ("", "none", "null"):
            return default
        try:
            return float(val)
        except (ValueError, TypeError) as e:
            raise ConfigError(
                f"Invalid value for '{field_name}': '{val}'. Must be a valid number."
            ) from e

    def to_int(val: Any, field_name: str, default: Optional[int]) -> Optional[int]:
        if val is None or str(val).strip().lower() in ("", "none", "null", "auto"):
            return default
        try:
            return int(val)
        except (ValueError, TypeError) as e:
            raise ConfigError(
                f"Invalid value for '{field_name}': '{val}'. Must be a valid integer."
            ) from e

    def to_bool(val: Any, default: bool) -> bool:
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in ("true", "1", "yes", "on")

    config = AppConfig(
        input_folder=to_path(raw_data.get("input_folder", "input")) or Path("input"),
        output_folder=to_path(raw_data.get("output_folder", "output")) or Path("output"),
        seconds_per_page=to_float(raw_data.get("seconds_per_page"), "seconds_per_page", 1.0),
        music_file=to_path(raw_data.get("music_file")),
        music_volume=to_float(raw_data.get("music_volume"), "music_volume", 0.15),
        music_fade_out_seconds=to_float(raw_data.get("music_fade_out_seconds"), "music_fade_out_seconds", 2.0),
        render_width=to_int(raw_data.get("render_width"), "render_width", 1920) or 1920,
        background_color=str(raw_data.get("background_color", "#FFFFFF")),
        fps=to_int(raw_data.get("fps"), "fps", 2) or 2,
        crf=to_int(raw_data.get("crf"), "crf", 23) if raw_data.get("crf") is not None else 23,
        preset=str(raw_data.get("preset", "slow")),
        audio_bitrate=str(raw_data.get("audio_bitrate", "64k")),
        audio_channels=str(raw_data.get("audio_channels", "stereo")),
        workers=to_int(raw_data.get("workers"), "workers", None),
        recursive=to_bool(raw_data.get("recursive"), False),
        overwrite=to_bool(raw_data.get("overwrite"), False),
        log_file=to_path(raw_data.get("log_file")),
        ffmpeg_path=to_path(raw_data.get("ffmpeg_path")),
    )

    config.validate(base_dir=base_dir)
    return config
