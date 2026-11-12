"""Tests for batch discovery, skip logic, dry run, and error containment."""

import tempfile
import unittest
from pathlib import Path
import pymupdf

from pdf2video.batch import (
    determine_worker_count,
    discover_pdf_files,
    process_batch,
)
from pdf2video.config import AppConfig


class TestBatchAndEncoder(unittest.TestCase):
    """Test suite for batch processing behavior and error isolation."""

    def test_discover_pdf_files_single_and_folder(self):
        """Discover PDF files correctly from single file and directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            p1 = base / "file1.pdf"
            p2 = base / "file2.PDF"
            sub = base / "subdir"
            sub.mkdir()
            p3 = sub / "file3.pdf"
            txt = base / "note.txt"

            p1.write_bytes(b"%PDF-1.4 test")
            p2.write_bytes(b"%PDF-1.4 test")
            p3.write_bytes(b"%PDF-1.4 test")
            txt.write_text("not a pdf", encoding="utf-8")

            # Single file
            found_single = discover_pdf_files(p1)
            self.assertEqual(len(found_single), 1)
            self.assertEqual(found_single[0].resolve(), p1.resolve())

            # Non-recursive directory
            found_non_rec = discover_pdf_files(base, recursive=False)
            self.assertEqual(len(found_non_rec), 2)

            # Recursive directory
            found_rec = discover_pdf_files(base, recursive=True)
            self.assertEqual(len(found_rec), 3)

    def test_determine_worker_count(self):
        """Worker count calculation handles auto and custom counts."""
        self.assertEqual(determine_worker_count(4), 4)
        auto_count = determine_worker_count(None)
        self.assertGreaterEqual(auto_count, 1)

    def test_dry_run_does_not_create_files(self):
        """Dry-run mode lists intended tasks without executing encoding."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            in_dir = tmp / "input"
            out_dir = tmp / "output"
            in_dir.mkdir()

            pdf_path = in_dir / "sample.pdf"
            doc = pymupdf.open()
            doc.new_page(width=400, height=400)
            doc.save(str(pdf_path))
            doc.close()

            cfg = AppConfig(
                input_folder=in_dir,
                output_folder=out_dir,
            )

            exit_code, results = process_batch(cfg, dry_run=True)
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "skipped")
            self.assertFalse((out_dir / "sample.mp4").exists())

    def test_batch_error_containment(self):
        """A corrupted PDF in a batch must not stop valid PDFs from converting."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            in_dir = tmp / "input"
            out_dir = tmp / "output"
            in_dir.mkdir()

            # 1. Valid PDF
            valid_pdf = in_dir / "valid.pdf"
            doc = pymupdf.open()
            page = doc.new_page(width=500, height=500)
            page.insert_text(pymupdf.Point(50, 50), "Valid Page")
            doc.save(str(valid_pdf))
            doc.close()

            # 2. Corrupted file with .pdf extension
            broken_pdf = in_dir / "corrupted.pdf"
            broken_pdf.write_bytes(b"CORRUPTED TRASH DATA NOT A PDF")

            cfg = AppConfig(
                input_folder=in_dir,
                output_folder=out_dir,
                seconds_per_page=0.5,
                workers=1,
            )

            exit_code, results = process_batch(cfg)

            # Valid should succeed
            valid_res = next(r for r in results if r.input_path.name == "valid.pdf")
            self.assertEqual(valid_res.status, "succeeded")
            self.assertTrue((out_dir / "valid.mp4").is_file())

            # Broken should fail with clear reason
            broken_res = next(r for r in results if r.input_path.name == "corrupted.pdf")
            self.assertEqual(broken_res.status, "failed")
            self.assertIn("Failed to open PDF", broken_res.reason)

            # Overall exit code is 1 because one file failed
            self.assertEqual(exit_code, 1)


    def test_default_folders_auto_creation(self):
        """Default input and music directories should be created automatically if missing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            in_dir = tmp / "missing_input"
            out_dir = tmp / "missing_output"
            cfg = AppConfig(
                input_folder=in_dir,
                output_folder=out_dir,
            )
            exit_code, results = process_batch(cfg, dry_run=True)
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_dir.is_dir())

    def test_single_pdf_direct_mp4_output(self):
        """Single PDF conversion should accept a direct output filename ending in .mp4."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            in_pdf = tmp / "single.pdf"
            out_mp4 = tmp / "custom_name.mp4"

            doc = pymupdf.open()
            doc.new_page(width=400, height=400)
            doc.save(str(in_pdf))
            doc.close()

            cfg = AppConfig(
                input_folder=in_pdf,
                output_folder=out_mp4,
                seconds_per_page=0.5,
            )
            exit_code, results = process_batch(cfg)
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_mp4.is_file())
            self.assertEqual(results[0].output_path.resolve(), out_mp4.resolve())

    def test_fast_slide_duration_fps_adjustment(self):
        """Fast slide durations (seconds_per_page < 1/fps) should increase fps to prevent dropping frames."""
        from PIL import Image
        from pdf2video.encoder import encode_video
        from pdf2video.ffmpeg_check import find_ffmpeg, FFmpegNotFoundError

        try:
            ffmpeg_exe = find_ffmpeg()
        except FFmpegNotFoundError:
            self.skipTest("FFmpeg not available")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            frames_dir = tmp / "frames"
            frames_dir.mkdir()
            for idx in range(5):
                Image.new("RGB", (100, 100), (idx * 40, 50, 50)).save(frames_dir / f"page_{idx:05d}.png")

            out_vid = tmp / "fast_slides.mp4"
            encode_video(
                ffmpeg_exe=ffmpeg_exe,
                frames_dir=frames_dir,
                num_pages=5,
                seconds_per_page=0.2,
                output_file=out_vid,
                fps=2,
            )
            self.assertTrue(out_vid.is_file())
            self.assertGreater(out_vid.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
