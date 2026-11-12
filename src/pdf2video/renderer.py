"""PDF rendering module using PyMuPDF and Pillow."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple
from PIL import Image, ImageColor
import pymupdf

logger = logging.getLogger(__name__)


class RenderError(Exception):
    """Base exception for PDF rendering failures."""
    pass


class EmptyPDFError(RenderError):
    """Raised when PDF contains zero pages."""
    pass


class PasswordProtectedPDFError(RenderError):
    """Raised when PDF is encrypted and requires a password."""
    pass


class CorruptedPDFError(RenderError):
    """Raised when PDF file is damaged or cannot be parsed."""
    pass


def get_canvas_dimensions(doc: pymupdf.Document, target_width: int) -> Tuple[int, int]:
    """Calculate consistent even canvas dimensions across all pages in a document.

    Args:
        doc: Open PyMuPDF document.
        target_width: Desired target horizontal resolution.

    Returns:
        (canvas_width, canvas_height) as even integers.
    """
    canvas_w = target_width if target_width % 2 == 0 else target_width + 1
    max_h = 0

    for page in doc:
        rect = page.rect
        if rect.width <= 0 or rect.height <= 0:
            raise CorruptedPDFError(
                f"Page {page.number + 1} has invalid dimensions ({rect.width}x{rect.height})"
            )
        scale = canvas_w / rect.width
        matrix = pymupdf.Matrix(scale, scale)
        trans_rect = rect.transform(matrix)
        h = int(trans_rect.round().height)
        if h % 2 != 0:
            h += 1
        if h > max_h:
            max_h = h

    if max_h == 0:
        max_h = canvas_w

    return canvas_w, max_h


def render_pdf_to_images(
    pdf_path: Path,
    output_dir: Path,
    target_width: int = 1920,
    background_color: str = "#FFFFFF",
) -> Tuple[int, Tuple[int, int]]:
    """Render each PDF page to an individual PNG image file.

    Pages are rendered one at a time and written directly to disk to minimize
    memory consumption. Differing aspect ratios are letterboxed onto a consistent
    canvas using background_color without stretching.

    Args:
        pdf_path: Path to the input PDF file.
        output_dir: Directory where rendered page images will be stored.
        target_width: Horizontal width of rendered pages in pixels (default 1920).
        background_color: Canvas background color for padding (default "#FFFFFF").

    Returns:
        Tuple of (page_count, (canvas_width, canvas_height)).

    Raises:
        CorruptedPDFError: If file is damaged or unreadable.
        PasswordProtectedPDFError: If file is encrypted.
        EmptyPDFError: If file contains no pages.
    """
    pdf_path = Path(pdf_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.is_file():
        raise CorruptedPDFError(f"PDF file does not exist: {pdf_path}")

    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as e:
        raise CorruptedPDFError(f"Failed to open PDF '{pdf_path.name}': {e}") from e

    try:
        # Check encryption
        if doc.is_encrypted:
            # Try authenticating with empty password in case of default permissions
            if not doc.authenticate(""):
                raise PasswordProtectedPDFError(
                    f"PDF '{pdf_path.name}' is password-protected and cannot be opened."
                )

        num_pages = len(doc)
        if num_pages == 0:
            raise EmptyPDFError(f"PDF '{pdf_path.name}' contains 0 pages.")

        # Determine canvas dimensions across all pages
        canvas_w, canvas_h = get_canvas_dimensions(doc, target_width)

        # Parse background color
        try:
            bg_rgb = ImageColor.getrgb(background_color)
        except Exception:
            bg_rgb = (255, 255, 255)

        logger.debug(
            "Rendering %d pages from '%s' onto canvas %dx%d",
            num_pages,
            pdf_path.name,
            canvas_w,
            canvas_h,
        )

        # Render each page one-by-one to avoid high memory spikes
        for page_idx in range(num_pages):
            page = doc[page_idx]
            rect = page.rect
            scale = canvas_w / rect.width
            matrix = pymupdf.Matrix(scale, scale)

            # PyMuPDF renders with built-in text and graphics anti-aliasing
            pix = page.get_pixmap(matrix=matrix, alpha=False, annots=True)
            frame_path = output_dir / f"page_{page_idx:05d}.png"

            if pix.width == canvas_w and pix.height == canvas_h:
                pix.save(str(frame_path))
            else:
                # Pad/letterbox page onto the uniform canvas
                canvas = Image.new("RGB", (canvas_w, canvas_h), bg_rgb)
                page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                offset_x = max(0, (canvas_w - pix.width) // 2)
                offset_y = max(0, (canvas_h - pix.height) // 2)
                canvas.paste(page_img, (offset_x, offset_y))
                canvas.save(str(frame_path), format="PNG")
                del page_img
                del canvas

            del pix

        return num_pages, (canvas_w, canvas_h)

    finally:
        doc.close()
