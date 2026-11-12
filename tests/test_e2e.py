"""End-to-end integration test creating a real video and verifying duration, audio, and skip logic."""

import subprocess
import tempfile
import unittest
from pathlib import Path
import pymupdf

from pdf2video.batch import process_batch
from pdf2video.config import AppConfig
from pdf2video.ffmpeg_check import FFmpegNotFoundError, find_ffmpeg


class TestEndToEnd(unittest.TestCase):
    """End-to-end conversion verification using actual FFmpeg encoding."""

    @classmethod
    def setUpClass(cls):
        """Skip integration test suite if FFmpeg is unavailable."""
        try:
            cls.ffmpeg_exe = find_ffmpeg()
        except FFmpegNotFoundError:
            raise unittest.SkipTest("FFmpeg executable not available on this machine.")

    def test_end_to_end_conversion_and_verification(self):
        """Convert a 3-page test PDF with audio and verify duration, audio track, and skip logic."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            in_dir = tmp / "input"
            out_dir = tmp / "output"
            in_dir.mkdir()

            # 1. Generate 3-page sample PDF
            pdf_path = in_dir / "e2e_document.pdf"
            doc = pymupdf.open()
            for idx in range(3):
                p = doc.new_page(width=600, height=800)
                p.draw_rect(pymupdf.Rect(40, 40, 560, 760), color=(0.1, 0.3, 0.7), fill=(0.95, 0.95, 1.0))
                p.insert_text(pymupdf.Point(80, 150), f"Test Document Page {idx + 1}", fontsize=22)
                p.insert_text(pymupdf.Point(80, 220), "Sharp text anti-aliased rendering verification.", fontsize=14)
            doc.save(str(pdf_path))
            doc.close()

            # 2. Use existing audio file if available, or generate a 1-second silence/tone
            audio_source = Path("light_music-cosmic-ambient-236235.mp3").resolve()
            test_audio = None
            if audio_source.is_file():
                test_audio = audio_source
            else:
                # Generate a short 2-second wav file using ffmpeg
                gen_audio = tmp / "synth.wav"
                subprocess.run(
                    [
                        str(self.ffmpeg_exe),
                        "-y",
                        "-f", "lavfi",
                        "-i", "sine=frequency=440:duration=2",
                        str(gen_audio),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if gen_audio.is_file():
                    test_audio = gen_audio

            seconds_per_page = 1.5
            expected_duration = 3 * seconds_per_page  # 4.5 seconds

            cfg = AppConfig(
                input_folder=in_dir,
                output_folder=out_dir,
                seconds_per_page=seconds_per_page,
                music_file=test_audio,
                music_volume=0.20,
                music_fade_out_seconds=1.5,
                render_width=1920,
                fps=2,
                crf=23,
                overwrite=False,
            )

            # --- RUN 1: Full conversion ---
            exit_code, results = process_batch(cfg)
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "succeeded")
            self.assertEqual(results[0].page_count, 3)

            out_video = out_dir / "e2e_document.mp4"
            self.assertTrue(out_video.is_file())
            self.assertGreater(out_video.stat().st_size, 0)

            # Verify with FFmpeg inspection
            inspect_proc = subprocess.run(
                [str(self.ffmpeg_exe), "-i", str(out_video)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            stderr_text = inspect_proc.stderr

            # Check duration: should be 00:00:04.50
            self.assertIn("Duration: 00:00:04.50", stderr_text)

            # Check video stream format
            self.assertIn("Video: h264", stderr_text)
            self.assertIn("yuv420p", stderr_text)

            # Check audio stream if audio was included
            if test_audio:
                self.assertIn("Audio: aac", stderr_text)

            # --- RUN 2: Skip logic verification ---
            exit_code_skip, results_skip = process_batch(cfg)
            self.assertEqual(exit_code_skip, 0)
            self.assertEqual(len(results_skip), 1)
            self.assertEqual(results_skip[0].status, "skipped")
            self.assertEqual(results_skip[0].reason, "Output file already exists")

            # --- RUN 3: Overwrite verification ---
            cfg_overwrite = AppConfig(
                input_folder=in_dir,
                output_folder=out_dir,
                seconds_per_page=seconds_per_page,
                music_file=test_audio,
                overwrite=True,
            )
            exit_code_ow, results_ow = process_batch(cfg_overwrite)
            self.assertEqual(exit_code_ow, 0)
            self.assertEqual(len(results_ow), 1)
            self.assertEqual(results_ow[0].status, "succeeded")


if __name__ == "__main__":
    unittest.main()
