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

## Architecture Guidance

Keep the document model and editor state separate.

The document model is persistent label data: label profile, objects, object geometry, text content, image references, font settings, and other data that would be saved with a label file someday. Keep it free of Qt imports and UI-only concepts.

Editor state is temporary UI state: selected object, editing object, hover object, dragging object, resize handle, drag origin, and similar interaction-only state. Do not bake transient editor state into saved label content.

## Shared Object Geometry

All document objects should share rectangular geometry:

- x
- y
- width
- height
- rotation
- selected, while still treated as editor/UI state unless persistence is intentionally added later

This shared geometry should support future move, resize, snapping, alignment, centering, and smart guides. Geometry is important because Label Pad should behave as a true WYSIWYG label maker.

## WYSIWYG and Scaling

The screen preview does not need to display labels at exact physical size by default. A 2 x 1 label at literal size may be uncomfortable to edit on screen.

However, the preview must preserve true relative scaling. What the user sees on screen should match what prints on the label proportionally:

- object positions
- relative object sizes
- text box bounds
- image bounds
- spacing
- alignment
- label margins

Avoid accidental scaling differences between preview, PDF export, and printed output. Users should not have to waste multiple labels to discover that printed placement differs from the preview.

Future zoom modes should be explicit, such as:

- Fit to window
- Actual size / 100% physical preview, possibly calibrated
- Zoomed editing views

Do not let zoom level change document geometry. Zoom is a view concern only.

## Long-Term Design Principles

Keep saved label data plain, explicit, and file-based when persistence is eventually added. Avoid turning Label Pad into a database, template library, or document-management system.

Prefer predictable direct manipulation over modes. When modes are needed, make the state boundaries clear in code and tests.

Preview, PDF export, and printed output should remain true WYSIWYG relative to one another. A fix that only improves one output path should be treated carefully unless the difference is intentional and documented.

Implementation planning belongs in `ROADMAP.md`; keep this file focused on durable project guidance.

## Project Notes

- Source code lives in `src/label_pad`.
- Tests live in `tests`.
- Keep changes small and covered by tests where practical.
- Prefer standard-library functionality unless the project already depends on a library.
