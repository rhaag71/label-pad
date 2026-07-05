# Label Pad Roadmap

## Vision

A small, fast desktop label editor for thermal printers.

The goal is to make creating and printing labels effortless while remaining intentionally small and maintainable.

The application should feel closer to Notepad than Microsoft Word.

---

## Current Milestone

### Milestone 6 — Shared Object Geometry

Objectives:

- Completed: shared object geometry (x, y, width, height, rotation)
- Completed: drag to move selected object
- Completed: bottom-right resize handle
- Active: text wrapping
- Upcoming: basic font selection
- Upcoming: basic text formatting
- Upcoming: image objects using the same geometry model

Definition of Done:

- Preview matches PDF.
- PDF matches printed label.
- Geometry is shared between text and images.
- Tests pass.
- Ruff passes.

---

## Completed Milestones

- Project scaffold: package layout, development dependencies, tests, and linting.
- Printer/profile infrastructure: label profiles, profile selection, and printer-facing setup.
- Document model: in-memory label documents with typed label objects and document defaults.
- Renderer architecture: shared rendering path with separate preview and PDF contexts.
- Preview rendering: white label preview with proportional layout.
- PDF rendering: export path for printable labels.
- Text object creation: double-click empty label space creates default text and starts editing.
- Selection model: single-click selects existing text boxes; empty/outside clicks clear selection.
- Inline editing: selected text can be edited in-place with commit/cancel behavior.
- Current interaction model: single-click selects or clears, double-click edits or creates, Delete removes selected objects when not editing.

This is a milestone summary, not a changelog.

---

## Future Milestones

Potential future work includes:

- Save/Open labels
- Clipboard support
- Copy/paste whole selected boxes
- Drag & Drop images
- Alignment tools
- Snap to guides
- Smart guides
- Multi-select
- Zoom
- Actual-size preview
- Undo/Redo
- Rotation
- Additional object types

No implementation order is promised beyond the current milestone.

---

## Notes

- Geometry should be shared across all object types.
- Editor state should remain separate from document data.
- MVP text boxes should default to 14 pt text.
- Screen zoom must never affect document geometry.
- Preview, PDF, and printed labels should remain true WYSIWYG relative to one another.
- Simplicity remains more important than feature count.
