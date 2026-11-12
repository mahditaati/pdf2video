"""Tests for configuration parsing, defaults, and validation."""

import tempfile
import unittest
from pathlib import Path
import yaml

from pdf2video.config import AppConfig, ConfigError, load_config


class TestConfig(unittest.TestCase):
    """Test suite for config loading and validation rules."""

    def test_default_config(self):
        """Verify default configuration has expected parameters."""
        cfg = AppConfig()
        self.assertEqual(cfg.input_folder, Path("input"))
        self.assertEqual(cfg.output_folder, Path("output"))
        self.assertEqual(cfg.seconds_per_page, 1.0)
        self.assertIsNone(cfg.music_file)
        self.assertEqual(cfg.music_volume, 0.15)
        self.assertEqual(cfg.music_fade_out_seconds, 2.0)
        self.assertEqual(cfg.render_width, 1920)
        self.assertEqual(cfg.background_color, "#FFFFFF")
        self.assertEqual(cfg.fps, 2)
        self.assertEqual(cfg.crf, 23)
        self.assertEqual(cfg.preset, "slow")
        self.assertEqual(cfg.audio_bitrate, "64k")
        self.assertEqual(cfg.audio_channels, "stereo")
        self.assertIsNone(cfg.workers)
        self.assertFalse(cfg.recursive)
        self.assertFalse(cfg.overwrite)
        self.assertIsNone(cfg.log_file)
        self.assertIsNone(cfg.ffmpeg_path)

    def test_load_config_from_yaml(self):
        """Verify loading settings from custom YAML file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / "test_config.yaml"
            data = {
                "seconds_per_page": 2.5,
                "render_width": 1280,
                "fps": 5,
                "crf": 20,
                "preset": "fast",
                "background_color": "#000000",
                "recursive": True,
                "overwrite": True,
            }
            with open(cfg_file, "w", encoding="utf-8") as f:
                yaml.dump(data, f)

            loaded = load_config(cfg_file)
            self.assertEqual(loaded.seconds_per_page, 2.5)
            self.assertEqual(loaded.render_width, 1280)
            self.assertEqual(loaded.fps, 5)
            self.assertEqual(loaded.crf, 20)
            self.assertEqual(loaded.preset, "fast")
            self.assertEqual(loaded.background_color, "#000000")
            self.assertTrue(loaded.recursive)
            self.assertTrue(loaded.overwrite)

    def test_cli_overrides_yaml(self):
        """Verify CLI overrides take precedence over YAML config values."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / "test_config.yaml"
            data = {"seconds_per_page": 2.0, "crf": 28}
            with open(cfg_file, "w", encoding="utf-8") as f:
                yaml.dump(data, f)

            overrides = {"seconds_per_page": 0.5, "crf": 18}
            loaded = load_config(cfg_file, overrides=overrides)
            self.assertEqual(loaded.seconds_per_page, 0.5)
            self.assertEqual(loaded.crf, 18)

    def test_invalid_seconds_per_page(self):
        """Negative or zero duration should raise ConfigError."""
        cfg = AppConfig(seconds_per_page=0.0)
        with self.assertRaises(ConfigError):
            cfg.validate()

        cfg_neg = AppConfig(seconds_per_page=-1.0)
        with self.assertRaises(ConfigError):
            cfg_neg.validate()

    def test_invalid_music_volume(self):
        """Negative music volume should raise ConfigError."""
        cfg = AppConfig(music_volume=-0.1)
        with self.assertRaises(ConfigError):
            cfg.validate()

    def test_invalid_crf(self):
        """CRF outside 0-51 should raise ConfigError."""
        with self.assertRaises(ConfigError):
            AppConfig(crf=-1).validate()

        with self.assertRaises(ConfigError):
            AppConfig(crf=52).validate()

    def test_invalid_preset(self):
        """Non-existent preset should raise ConfigError."""
        with self.assertRaises(ConfigError):
            AppConfig(preset="ludicrous_speed").validate()

    def test_invalid_channels(self):
        """Invalid audio channel descriptor should raise ConfigError."""
        with self.assertRaises(ConfigError):
            AppConfig(audio_channels="surround_7_1").validate()

    def test_invalid_background_color(self):
        """Unparseable color name should raise ConfigError."""
        with self.assertRaises(ConfigError):
            AppConfig(background_color="not_a_real_color_xyz").validate()

    def test_missing_explicit_music_file(self):
        """Explicitly specifying a non-existent music file should raise ConfigError."""
        cfg = AppConfig(music_file=Path("non_existent_music_12345.mp3"))
        with self.assertRaises(ConfigError):
            cfg.validate()

    def test_missing_explicit_input_pdf(self):
        """Specifying a non-existent PDF file as input should raise ConfigError."""
        cfg = AppConfig(input_folder=Path("missing_file.pdf"))
        with self.assertRaises(ConfigError):
            cfg.validate()

    def test_invalid_audio_bitrate(self):
        """Invalid audio bitrate format should raise ConfigError."""
        cfg = AppConfig(audio_bitrate="invalid_rate")
        with self.assertRaises(ConfigError):
            cfg.validate()

    def test_workers_parsing_auto_and_string(self):
        """'workers: auto' should parse to None and string integers to int."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / "cfg.yaml"
            with open(cfg_file, "w", encoding="utf-8") as f:
                yaml.dump({"workers": "auto"}, f)
            loaded = load_config(cfg_file)
            self.assertIsNone(loaded.workers)

            with open(cfg_file, "w", encoding="utf-8") as f:
                yaml.dump({"workers": "4"}, f)
            loaded4 = load_config(cfg_file)
            self.assertEqual(loaded4.workers, 4)

    def test_non_numeric_fields_raise_config_error(self):
        """Non-numeric string values in numeric config options should raise ConfigError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / "cfg.yaml"
            with open(cfg_file, "w", encoding="utf-8") as f:
                yaml.dump({"crf": "ultra_sharp"}, f)
            with self.assertRaises(ConfigError):
                load_config(cfg_file)

            with open(cfg_file, "w", encoding="utf-8") as f:
                yaml.dump({"seconds_per_page": "fast"}, f)
            with self.assertRaises(ConfigError):
                load_config(cfg_file)


if __name__ == "__main__":
    unittest.main()
