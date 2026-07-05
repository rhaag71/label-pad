# AGENTS.md

## Philosophy

Label Pad is Notepad, not Word.

The app should stay small, fast, and reliable. Prefer plain workflows, obvious UI, and boring implementation choices over broad feature surfaces. When in doubt, keep the MVP focused on making and printing simple labels.

Avoid feature creep. New code should make the core label workflow clearer, safer, or easier to maintain.

## Non-Goals

Do not add:

- Barcode or QR generation
- Image editing
- Drawing tools
- Database features
- Project files
- Document management
- Template libraries

## Project Notes

- Source code lives in `src/label_pad`.
- Tests live in `tests`.
- Keep changes small and covered by tests where practical.
- Prefer standard-library functionality unless the project already depends on a library.
