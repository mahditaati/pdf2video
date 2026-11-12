"""Tests for duration calculations, audio fade math, and music discovery."""

import tempfile
import unittest
from pathlib import Path

from pdf2video.audio import (
    auto_detect_music_file,
    build_audio_filter,
    calculate_fade_out,
)


class TestDurationAndAudio(unittest.TestCase):
    """Test suite for duration and audio filter mechanics."""

    def test_fade_out_when_video_is_longer_than_fade(self):
        """Fade-out should start at (duration - fade) when duration > fade."""
        total_duration = 10.0
        fade_seconds = 2.0
        start, duration = calculate_fade_out(total_duration, fade_seconds)
        self.assertAlmostEqual(start, 8.0)
        self.assertAlmostEqual(duration, 2.0)

    def test_fade_out_capped_at_video_duration(self):
        """Fade-out duration must never exceed the video length itself."""
        total_duration = 1.0
        fade_seconds = 2.0
        start, duration = calculate_fade_out(total_duration, fade_seconds)
        self.assertAlmostEqual(start, 0.0)
        self.assertAlmostEqual(duration, 1.0)

    def test_fade_out_zero_duration(self):
        """Fade-out with 0 seconds should return (total_duration, 0.0)."""
        start, duration = calculate_fade_out(5.0, 0.0)
        self.assertAlmostEqual(start, 5.0)
        self.assertAlmostEqual(duration, 0.0)

    def test_build_audio_filter_syntax(self):
        """Audio filter string should format volume and afade timestamps accurately."""
        filter_str = build_audio_filter(volume=0.15, total_duration=8.0, fade_out_seconds=2.0)
        self.assertIn("volume=0.150", filter_str)
        self.assertIn("afade=t=out:st=6.000:d=2.000", filter_str)

    def test_auto_detect_music_file(self):
        """Detect music file in search directory and ignore non-audio files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir)
            (dir_path / "document.txt").write_text("not audio", encoding="utf-8")
            (dir_path / "image.png").write_bytes(b"fake image")
            track_path = dir_path / "ambient.mp3"
            track_path.write_bytes(b"fake audio data")

            detected = auto_detect_music_file(search_dirs=[dir_path])
            self.assertIsNotNone(detected)
            self.assertEqual(detected.resolve(), track_path.resolve())

    def test_auto_detect_empty_returns_none(self):
        """Return None when no audio file exists in search directories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            detected = auto_detect_music_file(search_dirs=[Path(tmp_dir)])
            self.assertIsNone(detected)

    def test_build_audio_filter_labeled_and_zero_fade(self):
        """Audio filter string should format stream labels and omit afade when fade is 0."""
        labeled = build_audio_filter(
            volume=0.2,
            total_duration=5.0,
            fade_out_seconds=1.0,
            input_label="1:a",
            output_label="a",
        )
        self.assertTrue(labeled.startswith("[1:a]"))
        self.assertTrue(labeled.endswith("[a]"))
        self.assertIn("volume=0.200", labeled)
        self.assertIn("afade=t=out:st=4.000:d=1.000", labeled)

        no_fade = build_audio_filter(volume=0.2, total_duration=5.0, fade_out_seconds=0.0)
        self.assertEqual(no_fade, "volume=0.200")
        self.assertNotIn("afade", no_fade)

    def test_probe_media_duration(self):
        """probe_media_duration should return valid positive duration for an audio file."""
        from pdf2video.audio import probe_media_duration
        from pdf2video.ffmpeg_check import find_ffmpeg, FFmpegNotFoundError

        try:
            ffmpeg_exe = find_ffmpeg()
        except FFmpegNotFoundError:
            self.skipTest("FFmpeg not available")

        sample_audio = Path("light_music-cosmic-ambient-236235.mp3").resolve()
        if sample_audio.is_file():
            duration = probe_media_duration(ffmpeg_exe, sample_audio)
            self.assertIsNotNone(duration)
            self.assertGreater(duration, 0)


if __name__ == "__main__":
    unittest.main()
