# 01: Default page and corpus dropdown

**What to build:** Opening the page on localhost already shows a roof, and the
power user can switch to any named corpus footprint and submit.

GET runs the 10 × 6 m rectangle at 45°: describe text (terrain flag, ridge
height 3 m, total sloped area, arc lengths by kind), then the plan, then the
orbitable 3D solid. Metres and degrees are visible. The HTML is a real form
template, Plotly.js comes from a CDN, and `roof` plus the existing plan and
solid views do the work. The core package still has no web framework and no I/O.

A dropdown lists the corpus by name — at least the rectangle, L, U, courtyard,
gabled rectangle, and bowtie — not a second hand-copied geometry list. Choosing
a name fills whatever form fields exist (coordinate and pitch tables once
ticket 03 adds them) and POST runs that fixture's rings, pitch, and overhang.

The bowtie is the Failure demo: `kind` is `self_intersection`, `reason` is shown,
the input footprint is drawn, and there is no plan of a roof and no 3D. The
courtyard and the gabled rectangle are terrain Roofs with 3D; the gabled plan
includes a verge.

This is the tracer bullet: Flask, a `web` extra, GET plus corpus POST, HTTP
tests through the Flask test client. No coordinate editor and no Cloud Run yet.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Stories:** 2, 3, 4, 5 (preset loads the fixture; tables in 03), 6, 7, 8, 20, 21, 22, 23, 25, 26, 27, 28, 32, 33, 34, 35, 36, 39

**Prior art:** ADR-0002. Feature PRD "One new seam, above the existing one",
"Flask and a Jinja template", "Figures are fragments, not write_html files",
"Presets are the corpus", and the GET / bowtie / courtyard / gabled rows of
"Required HTTP cases". Worked numbers: 10 × 6 m at 45° has a 4 m ridge at
height 3 m. Viz smoke tests (`test_plan_view_builds_from_a_roof`,
`test_solid_view_builds_from_a_roof`) — figures build, not pixels. `describe`
in the getting-started notebook is the quantity block to copy. Corpus fixtures
(`rectangle-10x6`, `l-shape`, `u-shape`, `courtyard`, `rectangle-gabled`,
`bowtie`, …). Failure `self_intersection` on the roof entry point. Notebook
Failure drawing — the web app owns it; do not add it to viz. Artifact homes
are already in the PRD: application under `web/`, `web` extra, README "Web
demo" section for the local command only.

- [ ] GET returns 200 and the default 10 × 6 m rectangle at 45° already run
- [ ] Describe reports a terrain, ridge height 3 m, and total sloped area matching `roof`
- [ ] Plan view and 3D solid are both present on that default roof
- [ ] Plotly.js is loaded from a CDN, not inlined by `write_html`
- [ ] The form lives in an HTML template a person can read
- [ ] Dropdown lists the corpus footprints by name, not a parallel coordinate list
- [ ] Submitting the bowtie returns Failure `self_intersection`, draws the input footprint, and omits 3D
- [ ] Submitting the courtyard returns a terrain Roof with plan and 3D
- [ ] Submitting the gabled rectangle returns a terrain Roof whose plan includes a verge, with 3D
- [ ] Picking a fixture loads that fixture's rings, pitch, and overhang into the form
- [ ] `import krovlab` still pulls in no third-party dependencies
- [ ] The core package does not import Flask or the web app
- [ ] One local command starts the server
- [ ] Flask test client covers the GET and the bowtie, courtyard, and gabled rectangle POSTs; nothing asserts on CSS or pixels
