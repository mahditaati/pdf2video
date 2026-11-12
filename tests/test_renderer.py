"""Tests for PDF rendering, aspect ratio handling, canvas padding, and error cases."""

import tempfile
import unittest
from pathlib import Path
from PIL import Image
import pymupdf

from pdf2video.renderer import (
    CorruptedPDFError,
    EmptyPDFError,
    PasswordProtectedPDFError,
    get_canvas_dimensions,
    render_pdf_to_images,
)


class TestRenderer(unittest.TestCase):
    """Test suite for PyMuPDF page rendering logic."""

    def test_single_page_rendering_and_even_dimensions(self):
        """Rendered single page should have exact target width and even height."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "single_test.pdf"
            doc = pymupdf.open()
            page = doc.new_page(width=500, height=750)
            page.insert_text(pymupdf.Point(50, 100), "Hello Test Page", fontsize=18)
            doc.save(str(pdf_path))
            doc.close()

            frames_dir = Path(tmp_dir) / "frames"
            num_pages, (canvas_w, canvas_h) = render_pdf_to_images(
                pdf_path=pdf_path,
                output_dir=frames_dir,
                target_width=1920,
            )

            self.assertEqual(num_pages, 1)
            self.assertEqual(canvas_w, 1920)
            self.assertEqual(canvas_w % 2, 0)
            self.assertEqual(canvas_h % 2, 0)

            frame_file = frames_dir / "page_00000.png"
            self.assertTrue(frame_file.is_file())

            with Image.open(frame_file) as img:
                self.assertEqual(img.size, (canvas_w, canvas_h))

    def test_mixed_aspect_ratio_padding(self):
        """Mixed aspect ratio pages must letterbox onto a uniform canvas without stretching."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "mixed_test.pdf"
            doc = pymupdf.open()
            # Page 1: Portrait (500x1000) -> at width 1920, height is 3840
            doc.new_page(width=500, height=1000)
            # Page 2: Landscape (1000x500) -> at width 1920, height is 960
            doc.new_page(width=1000, height=500)
            doc.save(str(pdf_path))
            doc.close()

            frames_dir = Path(tmp_dir) / "frames"
            num_pages, (canvas_w, canvas_h) = render_pdf_to_images(
                pdf_path=pdf_path,
                output_dir=frames_dir,
                target_width=1920,
                background_color="#FFFFFF",
            )

            self.assertEqual(num_pages, 2)
            self.assertEqual(canvas_w, 1920)
            self.assertEqual(canvas_h, 3840)

            with Image.open(frames_dir / "page_00000.png") as img0, Image.open(frames_dir / "page_00001.png") as img1:
                self.assertEqual(img0.size, (1920, 3840))
                self.assertEqual(img1.size, (1920, 3840))

    def test_empty_pdf_raises_error(self):
        """PDF with 0 pages should raise EmptyPDFError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "empty.pdf"
            empty_pdf_bytes = (
                b"%PDF-1.4\n"
                b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
                b"2 0 obj <</Type /Pages /Kids [] /Count 0>> endobj\n"
                b"xref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
                b"trailer <</Size 3 /Root 1 0 R>>\nstartxref\n115\n%%EOF\n"
            )
            pdf_path.write_bytes(empty_pdf_bytes)

            frames_dir = Path(tmp_dir) / "frames"
            with self.assertRaises(EmptyPDFError):
                render_pdf_to_images(pdf_path, frames_dir)

    def test_corrupted_pdf_raises_error(self):
        """Damaged or non-PDF bytes should raise CorruptedPDFError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "broken.pdf"
            pdf_path.write_bytes(b"NOT A REAL PDF HEADER")

            frames_dir = Path(tmp_dir) / "frames"
            with self.assertRaises(CorruptedPDFError):
                render_pdf_to_images(pdf_path, frames_dir)

    def test_password_protected_pdf_raises_error(self):
        """Encrypted PDF requiring a password should raise PasswordProtectedPDFError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "locked.pdf"
            doc = pymupdf.open()
            page = doc.new_page(width=400, height=400)
            page.insert_text(pymupdf.Point(50, 50), "Secret Content")
            # Encrypt with owner and user passwords
            perm = int(
                pymupdf.PDF_PERM_ACCESSIBILITY
                | pymupdf.PDF_PERM_PRINT
                | pymupdf.PDF_PERM_COPY
                | pymupdf.PDF_PERM_ANNOTATE
            )
            doc.save(
                str(pdf_path),
                encryption=pymupdf.PDF_ENCRYPT_AES_256,
                owner_pw="secret123",
                user_pw="secret123",
                permissions=perm,
            )
            doc.close()

            frames_dir = Path(tmp_dir) / "frames"
            with self.assertRaises(PasswordProtectedPDFError):
                render_pdf_to_images(pdf_path, frames_dir)

    def test_persian_and_unicode_filename(self):
        """Files with Persian or unicode names should be read and rendered without encoding errors."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "سند_تستی_نمونه.pdf"
            doc = pymupdf.open()
            p = doc.new_page(width=600, height=800)
            p.insert_text(pymupdf.Point(50, 100), "Unicode Filename Test", fontsize=16)
            doc.save(str(pdf_path))
            doc.close()

            frames_dir = Path(tmp_dir) / "frames"
            num_pages, dims = render_pdf_to_images(pdf_path, frames_dir)
            self.assertEqual(num_pages, 1)
            self.assertTrue((frames_dir / "page_00000.png").is_file())

    def test_fractional_dimension_no_overflow_or_crop(self):
        """Pages with non-integer point dimensions must not overflow canvas or get cropped."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "fractional.pdf"
            doc = pymupdf.open()
            # Standard ISO A4 dimensions in points
            p = doc.new_page(width=595.2755737304688, height=841.8897705078125)
            # Add an annotation
            annot = p.add_highlight_annot(pymupdf.Rect(50, 50, 200, 70))
            annot.update()
            p.insert_text(pymupdf.Point(50, 65), "Annotated Fractional Page", fontsize=12)
            doc.save(str(pdf_path))
            doc.close()

            frames_dir = Path(tmp_dir) / "frames"
            num_pages, (canvas_w, canvas_h) = render_pdf_to_images(
                pdf_path=pdf_path,
                output_dir=frames_dir,
                target_width=1920,
            )

            self.assertEqual(num_pages, 1)
            self.assertEqual(canvas_w, 1920)
            self.assertEqual(canvas_h % 2, 0)
            self.assertEqual(canvas_w % 2, 0)

            frame_img = frames_dir / "page_00000.png"
            self.assertTrue(frame_img.is_file())
            with Image.open(frame_img) as im:
                self.assertEqual(im.size, (canvas_w, canvas_h))


if __name__ == "__main__":
    unittest.main()
