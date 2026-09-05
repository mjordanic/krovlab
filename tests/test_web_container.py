"""Container contract for the form server.

The process that runs on localhost is the one Cloud Run starts: bind
0.0.0.0 and honour PORT. No live Google Cloud project.
"""

from pathlib import Path

import pytest
from web import __main__ as serve


def test_when_PORT_is_set_the_process_binds_all_interfaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        recorded["host"] = kwargs["host"]
        recorded["port"] = kwargs["port"]

    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setattr(serve.app, "run", fake_run)
    serve.main()
    assert recorded == {"host": "0.0.0.0", "port": 8080}


def test_without_PORT_the_process_listens_on_localhost_5000(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        recorded["host"] = kwargs["host"]
        recorded["port"] = kwargs["port"]

    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(serve.app, "run", fake_run)
    serve.main()
    assert recorded == {"host": "127.0.0.1", "port": 5000}


def test_dockerfile_starts_the_same_app_on_python_313() -> None:
    text = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    assert "python:3.13" in text
    assert "ENV PORT=8080" in text
    assert '"python", "-m", "web"' in text


def test_readme_documents_localhost_and_cloud_run_flags() -> None:
    text = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    assert "uv run --extra web python -m web" in text
    assert "europe-west1" in text
    assert "--min-instances 0" in text
    assert "--allow-unauthenticated" in text
