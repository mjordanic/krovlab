FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock README.md CONTEXT.md ./
COPY src src

RUN uv sync --frozen --no-dev --extra web --extra gnn

COPY web web
COPY docs/limitations.md docs/limitations.md
COPY tests/fixtures/footprints tests/fixtures/footprints
COPY models/ren2021-face-adjacency.pt models/ren2021-face-adjacency.pt

ENV PATH="/app/.venv/bin:$PATH"
# Cloud Run injects PORT. The process binds 0.0.0.0 and honours it.
ENV PORT=8080

CMD ["python", "-m", "web"]
