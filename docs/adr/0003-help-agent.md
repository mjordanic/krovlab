# 3. In-page help agent fills the form knobs

Date: 2026-09-11

## Status

Accepted.

## Context

ADR-0002 shipped one HTML form, no JSON API, no auth. The visitor edits
cells on that page and POSTs. A copilot that explains the current project
and turns the same knobs needs a language model and a way to write those
fields without scraping HTML.

The page stays the source of truth. The agent must not rebuild the roof
(the visitor still clicks **Update roof**). Owner-pays Gemini 3.6 Flash,
capped in AI Studio at about $10/month. The Cloud Run URL is unlisted;
the checkbox is not a lock.

## Decision

Add one JSON route, `POST /agent`, beside `GET|POST /`. The browser sends
the current form fields, the takeoff text already on the page, and the
chat so far. The server calls Gemini with tools that patch those fields.
The key is `GEMINI_API_KEY`. Locally, `python -m web` loads it from
`.env` without overriding the process environment. On Cloud Run it
comes from Secret Manager. If it is unset, the “Need help?” box is
omitted.

Tools are `inspect_project`, `set_wall`, and `set_cell`. They cannot draw
geometry. Prompt grounding is `CONTEXT.md`, `docs/limitations.md`, and
`README.md` stuffed into the system prompt — small enough that RAG is
unnecessary.

A per-IP rate limit and a token cap sit in front of Gemini. The provider
spend cap is the fuse. Per-IP limits are per Cloud Run instance.

## Consequences

`tests/test_web.py` no longer forbids every JSON route; it still forbids
a roof CRUD API. ADR-0002's form POST remains how a roof is built. The
container image must include the markdown files the prompt reads.
