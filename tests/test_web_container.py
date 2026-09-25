"""Container contract for the form server.

The process that runs on localhost is the one Cloud Run starts: bind
0.0.0.0 and honour PORT. No live Google Cloud project.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

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
    monkeypatch.setattr(serve, "load_repo_env", lambda: None)
    monkeypatch.setattr(
        serve, "create_app", lambda: SimpleNamespace(run=fake_run)
    )
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
    monkeypatch.setattr(serve, "load_repo_env", lambda: None)
    monkeypatch.setattr(
        serve, "create_app", lambda: SimpleNamespace(run=fake_run)
    )
    serve.main()
    assert recorded == {"host": "127.0.0.1", "port": 5000}


def test_load_repo_env_fills_unset_keys_from_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment\nGEMINI_API_KEY="local-test-key"\nEMPTY=\n',
        encoding="utf-8",
    )
    serve.load_repo_env(env_file)
    assert os.environ["GEMINI_API_KEY"] == "local-test-key"


def test_load_repo_env_skips_a_missing_file(tmp_path: Path) -> None:
    serve.load_repo_env(tmp_path / "no-such.env")


def test_load_repo_env_does_not_override_the_process_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=from-file\n", encoding="utf-8")
    serve.load_repo_env(env_file)
    assert os.environ["GEMINI_API_KEY"] == "from-shell"


def test_dotenv_sample_documents_the_gemini_key() -> None:
    text = (Path(__file__).resolve().parents[1] / ".env_sample").read_text()
    assert "GEMINI_API_KEY" in text


def test_dockerfile_starts_the_same_app_on_python_313() -> None:
    text = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    assert "python:3.13" in text
    assert "ENV PORT=8080" in text
    assert '"python", "-m", "web"' in text
    assert "CONTEXT.md" in text
    assert "docs/limitations.md" in text
    assert "--extra gnn" in text
    assert "models/ren2021-face-adjacency.pt" in text


def test_readme_documents_localhost_and_cloud_run_flags() -> None:
    text = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    assert "uv run --extra web python -m web" in text
    assert "europe-west1" in text
    assert "--min-instances 0" in text
    assert "--memory 2Gi" in text
    assert "--allow-unauthenticated" in text
    assert "GEMINI_API_KEY" in text
    assert "--set-secrets=GEMINI_API_KEY" in text
    assert ".env_sample" in text
