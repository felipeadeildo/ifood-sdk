"""Run the server over stdio, which is how a local MCP host launches it."""

from .server import build_server


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
