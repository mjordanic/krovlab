"""Run the form server: ``uv run --extra web python -m web``."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from web.app import create_app

_REPO_ROOT = Path(__file__).resolve().parents[1]


def load_repo_env(env_file: Path | None = None) -> None:
    """Load ``.env`` into os.environ. Existing variables win (Cloud Run, export)."""
    path = _REPO_ROOT / ".env" if env_file is None else env_file
    load_dotenv(path)


def main() -> None:
    load_repo_env()
    app = create_app()
    port = int(os.environ.get("PORT", "5000"))
    host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
