"""Run the form server: ``uv run --extra web python -m web``."""

from __future__ import annotations

import os

from web.app import create_app

app = create_app()


def main() -> None:
    port = int(os.environ.get("PORT", "5000"))
    host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
