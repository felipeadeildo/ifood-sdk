# Install

Python 3.14 or newer. The project uses `uv`.

```bash
git clone https://github.com/felipeadeildo/ifood-sdk
cd ifood-sdk
uv sync --all-groups --all-extras
```

The package is not on PyPI yet, so the clone is the install. Extras decide what you get:

| Extra | Adds | For |
|---|---|---|
| none | `httpx`, `pydantic`, `pydantic-settings` | the client |
| `mcp` | `mcp` | the MCP server |
| `api` | `fastapi`, `uvicorn` | the HTTP service |

```bash
pip install "ifood-sdk[api,mcp]"
```

Development checks:

```bash
uv run ruff check .
uv run ty check
uv run pytest
uv run prek run --all-files
```
