"""Run the form server: ``uv run --extra web python -m web``."""

from __future__ import annotations

from web.app import create_app

app = create_app()


def main() -> None:
    app.run(host="127.0.0.1", port=5000)


if __name__ == "__main__":
    main()
