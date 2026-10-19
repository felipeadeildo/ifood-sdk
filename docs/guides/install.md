# Install

Python 3.14 or newer. The project uses `uv`.

```bash
git clone https://github.com/felipeadeildo/ifood-sdk
cd ifood-sdk
uv sync --all-groups
```

The package is not on PyPI yet, so the clone is the install. The library lives in
`packages/sdk`; `uv sync` from the root wires it into the environment.

Dependencies are not pinned, so a fresh sync takes the current versions.

Development checks:

```bash
uv run ruff check .
uv run ty check
uv run pytest
uv run prek run --all-files
```
