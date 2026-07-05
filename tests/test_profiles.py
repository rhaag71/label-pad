from label_pad.profiles import LabelProfile, default_profile_index, load_profiles


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


def test_builtin_profiles_default_to_rollo_2_by_1() -> None:
    profiles = load_profiles()

    assert profiles[default_profile_index(profiles)].name == "Rollo 2 x 1"
    assert [profile.name for profile in profiles] == [
        "Rollo 2 x 1",
        "Rollo 2.25 x 1.25",
        "Rollo 4 x 6",
    ]


def test_builtin_rollo_profile_sizes_are_physical_label_sizes() -> None:
    profiles = {profile.name: profile for profile in load_profiles()}

    assert profiles["Rollo 2 x 1"].label_width_mm == 50.8
    assert profiles["Rollo 2 x 1"].label_height_mm == 25.4
    assert profiles["Rollo 2 x 1"].cups_page_size == "2x1"
    assert profiles["Rollo 2.25 x 1.25"].label_width_mm == 57.15
    assert profiles["Rollo 2.25 x 1.25"].label_height_mm == 31.75
    assert profiles["Rollo 2.25 x 1.25"].cups_page_size is None
    assert profiles["Rollo 4 x 6"].cups_page_size == "4x6"


def test_default_profile_index_falls_back_to_first_profile() -> None:
    profiles = [
        LabelProfile(
            name="Only Profile",
            page_width_mm=10,
            page_height_mm=20,
            label_width_mm=10,
            label_height_mm=20,
            columns=1,
            rows=1,
        )
    ]

    assert default_profile_index(profiles) == 0
