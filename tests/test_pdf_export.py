import re

from label_pad.pdf_export import export_pdf, page_size_points
from label_pad.profiles import LabelProfile


def test_export_pdf_writes_pdf_with_profile_page_size(tmp_path) -> None:
    profile = LabelProfile(
        name="Test",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )

    output_path = export_pdf(tmp_path / "labels.pdf", profile)

    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF-")
    assert _media_box(output_path.read_bytes()) == (0.0, 0.0, 283.4646, 141.7323)


def test_page_size_points_uses_profile_physical_size() -> None:
    profile = LabelProfile(
        name="Test",
        page_width_mm=101.6,
        page_height_mm=152.4,
        label_width_mm=101.6,
        label_height_mm=152.4,
        columns=1,
        rows=1,
    )

    width, height = page_size_points(profile)

    assert round(width, 4) == 288
    assert round(height, 4) == 432


def _media_box(pdf_data: bytes) -> tuple[float, float, float, float]:
    match = re.search(rb"/MediaBox\s*\[\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*\]", pdf_data)
    assert match is not None
    return tuple(round(float(value), 4) for value in match.groups())
