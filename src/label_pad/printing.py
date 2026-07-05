"""System printing through CUPS-compatible commands."""

from __future__ import annotations

import subprocess
from pathlib import Path


def print_pdf(
    path: str | Path,
    printer_name: str | None = None,
    page_size: str | None = None,
) -> Path:
    """Send a PDF to the system print spooler."""
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    command = ["lp"]
    if printer_name:
        command.extend(["-d", printer_name])
    if page_size:
        command.extend(["-o", f"PageSize={page_size}"])
    command.append(str(pdf_path))
    subprocess.run(command, check=True)
    return pdf_path
