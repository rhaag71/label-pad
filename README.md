# label-pad

Label layout and printing utility.

## Project Status

See [ROADMAP.md](ROADMAP.md) for current implementation status and planned milestones.

## Development

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the package with development dependencies:

```bash
pip install -e ".[dev]"
```

Run checks:

```bash
pytest
ruff check .
black --check .
```
