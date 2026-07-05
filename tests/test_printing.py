from label_pad.printing import print_pdf


def test_print_pdf_adds_cups_page_size_option(tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "label.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    calls = []

    def fake_run(command, check) -> None:
        calls.append((command, check))

    monkeypatch.setattr("subprocess.run", fake_run)

    result = print_pdf(pdf_path, printer_name="Rollo_X1038", page_size="2x1")

    assert result == pdf_path
    assert calls == [
        (
            [
                "lp",
                "-d",
                "Rollo_X1038",
                "-o",
                "PageSize=2x1",
                str(pdf_path),
            ],
            True,
        )
    ]
