FROM python:3.13-slim-bookworm

# Cursor copies the repo in; do not COPY the project here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
