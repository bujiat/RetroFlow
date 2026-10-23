"""stdio entry: python -m app.mcp

Changes to apps/api before importing settings, so .env loads when Cursor's
working directory is the repository root.
"""

import os
from pathlib import Path


def main() -> None:
    os.chdir(Path(__file__).resolve().parents[2])
    from app.mcp.server import create_server

    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
