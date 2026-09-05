# 2. Python form server wraps the core

Date: 2026-09-05

## Status

Accepted.

## Context

ADR-0001 left the web app unresolved: a Python server, Pyodide in the browser, or a TypeScript port. The core had to stay data-in/data-out so any of the three could wrap it. The first UI is now being built: a page a power user can open from a URL, without Jupyter, without changing the engine.

## Decision

Wrap `roof` in a Python HTTP server that serves one HTML page. The browser submits a form and gets a full HTML response back — describe text, a plan (or the input footprint when there is no roof), and a 3D solid only when the roof is a terrain. Plotly figures are produced by the existing viz module and embedded as HTML fragments; Plotly.js is loaded from a CDN so the server does not inline megabytes per request.

Develop on localhost. When a URL is needed, deploy the same process to Cloud Run (scale to zero, unauthenticated, `europe-west1`).

The core package does not import the web stack, does no I/O, and does not grow a second entry point. Gable remains `pitch = 90`.

## Considered options

**Streamlit / Gradio.** Fastest page, cheapest to write, teaches none of how webpages work, and was the point of this UI for the author.

**Pyodide on static hosting.** Fits €0 and a URL, but there is no server to learn from, and the author asked for a server.

**TypeScript port of the skeleton.** Changes the engine. Forbidden for this slice.

**JSON API plus a JavaScript frontend.** The usual next step after a form page, not the first page. More surface, more to debug, same `roof` call.

**Render Free.** $0, but a sleeping service takes on the order of a minute to wake — a bad first impression for the person who receives the link. Cloud Run's idle cost for this traffic is still ~$0 and the wake is seconds.

## Consequences

A `web` extra and a Flask application live beside the library, not inside it. Hosting needs a container and a Google Cloud project with billing enabled; localhost does not. Someone who finds the public Cloud Run URL can run roofs — there is no auth, and this app has nothing to steal.
