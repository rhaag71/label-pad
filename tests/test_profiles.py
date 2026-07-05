from label_pad.profiles import LabelProfile, load_profiles


def test_label_profile_counts_labels_per_page() -> None:
    profile = LabelProfile(
        name="Example",
        page_width_mm=210,
        page_height_mm=297,
        label_width_mm=70,
        label_height_mm=37,
        columns=3,
        rows=8,
    )

    assert profile.labels_per_page == 24


def test_load_profiles_from_yaml(tmp_path) -> None:
    profiles_path = tmp_path / "profiles.yml"
    profiles_path.write_text(
        """
profiles:
  - name: Test Label
    page_width_mm: 100
    page_height_mm: 150
    label_width_mm: 50
    label_height_mm: 30
    columns: 2
    rows: 5
""",
        encoding="utf-8",
    )

    profiles = load_profiles(profiles_path)

    assert profiles == [
        LabelProfile(
            name="Test Label",
            page_width_mm=100,
            page_height_mm=150,
            label_width_mm=50,
            label_height_mm=30,
            columns=2,
            rows=5,
        )
    ]
