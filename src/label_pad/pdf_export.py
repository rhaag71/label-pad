"""PDF export."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from label_pad.model import LabelDocument
from label_pad.profiles import LabelProfile
from label_pad.renderer import PdfRenderContext, Renderer

POINTS_PER_MM = 72 / 25.4


def mm_to_points(value: float) -> float:
    """Convert millimeters to PDF points."""
    return value * POINTS_PER_MM


def page_size_points(profile: LabelProfile) -> tuple[float, float]:
    """Return a profile's PDF page size in points."""
    return (mm_to_points(profile.page_width_mm), mm_to_points(profile.page_height_mm))


def export_pdf(
    path: str | Path,
    profile: LabelProfile,
    document: LabelDocument,
) -> Path:
    """Create a label PDF for the selected profile and document."""
    output_path = Path(path)
    width, height = page_size_points(profile)

    pdf = canvas.Canvas(str(output_path), pagesize=(width, height))
    pdf.setFillColorRGB(1, 1, 1)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)

    image = Image.new("RGB", (1, 1), "white")
    pdf.drawImage(ImageReader(image), 0, 0, width=width, height=height)
    Renderer().render(document, PdfRenderContext(pdf, page_height=height))
    pdf.showPage()
    pdf.save()
    return output_path
