"""Label profile models and YAML loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PROFILES_YAML = """
profiles:
  - name: Rollo 2 x 1
    page_width_mm: 50.8
    page_height_mm: 25.4
    label_width_mm: 50.8
    label_height_mm: 25.4
    columns: 1
    rows: 1
    cups_page_size: 2x1
  - name: Rollo 2.25 x 1.25
    page_width_mm: 57.15
    page_height_mm: 31.75
    label_width_mm: 57.15
    label_height_mm: 31.75
    columns: 1
    rows: 1
  - name: Rollo 4 x 6
    page_width_mm: 101.6
    page_height_mm: 152.4
    label_width_mm: 101.6
    label_height_mm: 152.4
    columns: 1
    rows: 1
    cups_page_size: 4x6
"""

DEFAULT_PROFILE_NAME = "Rollo 2 x 1"


@dataclass(frozen=True)
class LabelProfile:
    """Physical label sheet settings."""

    name: str
    page_width_mm: float
    page_height_mm: float
    label_width_mm: float
    label_height_mm: float
    columns: int
    rows: int
    cups_page_size: str | None = None

    @property
    def labels_per_page(self) -> int:
        """Return the total number of labels on one page."""
        return self.columns * self.rows


def load_profiles(path: str | Path | None = None) -> list[LabelProfile]:
    """Load label profiles from YAML."""
    raw_yaml = Path(path).read_text(encoding="utf-8") if path else DEFAULT_PROFILES_YAML
    data = yaml.safe_load(raw_yaml) or {}
    profile_data = data.get("profiles", [])
    if not isinstance(profile_data, list):
        raise ValueError("profiles must be a list")

    profiles = [_profile_from_mapping(item) for item in profile_data]
    if not profiles:
        raise ValueError("at least one profile is required")
    return profiles


def default_profile_index(profiles: list[LabelProfile]) -> int:
    """Return the preferred default profile index."""
    for index, profile in enumerate(profiles):
        if profile.name == DEFAULT_PROFILE_NAME:
            return index
    return 0


def _profile_from_mapping(data: Any) -> LabelProfile:
    if not isinstance(data, dict):
        raise ValueError("profile entries must be mappings")
    return LabelProfile(
        name=str(data["name"]),
        page_width_mm=float(data["page_width_mm"]),
        page_height_mm=float(data["page_height_mm"]),
        label_width_mm=float(data["label_width_mm"]),
        label_height_mm=float(data["label_height_mm"]),
        columns=int(data["columns"]),
        rows=int(data["rows"]),
        cups_page_size=data.get("cups_page_size"),
    )
