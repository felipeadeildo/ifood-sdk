# Install

Python 3.14 or newer. The project uses `uv`.

```bash
git clone <repo> ifood-sdk
cd ifood-sdk
uv sync --all-groups
```

Dependencies are not pinned, so a fresh sync takes the current versions.

Development checks:

```bash
uv run ruff check .
uv run ty check
uv run pytest
uv run prek run --all-files
```
