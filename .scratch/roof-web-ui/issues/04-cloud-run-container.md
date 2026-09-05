# 04: Cloud Run container

**What to build:** The same process that runs on localhost can be given a URL.
A Dockerfile runs it on Python 3.13, binds `0.0.0.0`, and honours `PORT`. The
README "Web demo" section says how to run locally and how to deploy to Cloud
Run: `europe-west1`, min instances 0, unauthenticated. No custom domain, no
auth, no live GCP project in CI.

A power user with the deployed URL sees the same page as localhost — that is
story 1, and it is only true once 03 is on the image.

**Blocked by:** 03

**Status:** ready-for-agent

**Stories:** 1, 37, 38

**Prior art:** ADR-0002 hosting consequences (container, billing on, scale to
zero). PRD "Hosting is Cloud Run, after localhost works" and "Do not require a
live Cloud Run project in CI." Artifact homes: `Dockerfile` at the repo root,
README "Web demo" section. Plotly-from-CDN from ticket 01 is what keeps egress
cheap; do not switch back to inlined `write_html`.

- [ ] A Dockerfile starts the Flask app on Python 3.13, `0.0.0.0`, and `PORT`
- [ ] README documents the local command and the Cloud Run flags (region, min instances 0, unauthenticated)
- [ ] CI does not require a Google Cloud project
- [ ] The image serves the same form page as localhost (no second app)
