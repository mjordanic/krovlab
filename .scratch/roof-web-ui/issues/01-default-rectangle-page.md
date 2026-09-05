# 01: Default rectangle page

**What to build:** Opening the page on localhost already shows a roof. The
10 × 6 m rectangle at 45° comes back as a terrain: describe text (terrain flag,
ridge height 3 m, total sloped area, arc lengths by kind), then the plan, then
the orbitable 3D solid. Metres and degrees are visible. The HTML is a real form
template, Plotly.js comes from a CDN, and `roof` plus the existing plan and
solid views do the work. The core package still has no web framework and no
I/O.

This is the tracer bullet: one GET, one Flask process, a `web` extra, HTTP tests
through the Flask test client. No dropdown, no coordinate editor, no Cloud Run
yet. A POST of the same default fields is allowed if GET and POST share a
route, but the power user must see the roof without filling anything in.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Stories:** 2, 3, 20, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39

**Prior art:** ADR-0002 (Python form server wraps the core). Feature PRD
"One new seam, above the existing one", "Flask and a Jinja template", "Figures
are fragments, not write_html files", and the GET row of "Required HTTP cases".
Worked numbers: 10 × 6 m at 45° has a 4 m ridge at height 3 m (README / roof
tests). Viz smoke tests (`test_plan_view_builds_from_a_roof`,
`test_solid_view_builds_from_a_roof`) set the bar — figures build, not pixels.
`describe` in the getting-started notebook is the quantity block to copy, not a
new type. Artifact homes are already in the PRD: application under `web/`,
`web` extra, README "Web demo" section for the local command only.

- [ ] GET returns 200 and the default 10 × 6 m rectangle at 45° already run
- [ ] Describe reports a terrain, ridge height 3 m, and total sloped area matching `roof`
- [ ] Plan view and 3D solid are both present
- [ ] Plotly.js is loaded from a CDN, not inlined by `write_html`
- [ ] The form lives in an HTML template a person can read
- [ ] `import krovlab` still pulls in no third-party dependencies
- [ ] The core package does not import Flask or the web app
- [ ] One local command starts the server
- [ ] Flask test client covers this GET; nothing asserts on CSS or pixels
