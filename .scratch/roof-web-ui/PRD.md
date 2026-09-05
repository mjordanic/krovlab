# PRD: Roof form server

Status: ready-for-agent

Vocabulary in this document is defined in `CONTEXT.md`. Terms are used in their
glossary sense — "footprint", "hole", "pitch", "roof", "face", "plan area",
"sloped area", "ridge", "hip", "valley", "eave", "verge", "overhang", "terrain",
"Failure" — and not loosely. Do not call the footprint an outline, and do not
call the describe block a message. Respects ADR-0001 (own weighted straight
skeleton, in Python) and ADR-0002 (Python form server wraps the core).

## Problem Statement

The library already turns a footprint and pitches into a roof, or a named
Failure, and can draw a plan and a 3D solid. The only interactive way to poke
it is a notebook. A power user who does not have the repo, Python, or Jupyter
cannot try a rectangle, an L, a courtyard, or a gable, and cannot see why a
bowtie is refused.

The author also wants to learn how a webpage actually works: an HTML form, an
HTTP POST, a server that calls the library and returns HTML. A Streamlit wrapper
would hide that. Porting the engine would not be "just add UI."

## Solution

A single page, served by a small Flask process, that wraps `roof` and the
existing Plotly views.

The visitor picks a named footprint from the project's corpus, or edits
coordinates (outer ring, and optionally one hole). They set an eaves overhang,
a pitch to apply to every edge, and then per-edge pitches — including a gable
checkbox, which is `pitch = 90`. They submit the form.

The response is the same page with the result filled in:

- A describe block in the notebook sense: on a Failure, `kind` and `reason`; on
  a Roof, whether it is a terrain, ridge height, total sloped area, arc lengths
  by kind, and `validity.reasons` when it is not a terrain.
- On a Failure: a drawing of the input footprint (and hole, if any). No plan of
  a roof, no 3D.
- On a Roof that is not a terrain: the plan view only, plus the validity
  reasons. Quantities in the describe block are shown but not to be trusted.
- On a Roof that is a terrain: the plan view, then the orbitable 3D solid.

The first visit already shows the 10 × 6 m rectangle at 45°, so a URL is a
demo, not an empty form. Overhang, when set, is passed through to `roof`; the
views receive the original rings as `walls` / `wall_holes` so the building
stays distinct from the eaves.

The process runs on localhost while the page is being built. When a URL is
needed, the same process is deployed to Cloud Run.

## User Stories

**Opening the page**

1. As a power user, I want to open a URL in a browser and see a roof without
   installing Python or Jupyter, so that I can judge the library from a link.
2. As a power user, I want the first load to already show the 10 × 6 m rectangle
   at 45°, so that I immediately see describe text, a plan, and a 3D solid.
3. As a developer, I want to run the same page on localhost with one command,
   so that I can learn the form and the server before any cloud account exists.

**Choosing a footprint**

4. As a power user, I want a dropdown of the project's corpus footprints, so
   that I can try a rectangle, an L, a U, a courtyard, a gabled rectangle, and a
   bowtie without typing vertices.
5. As a power user, I want picking a named footprint to fill the coordinate
   tables, the per-edge pitch rows, and the overhang from that fixture, so that
   the form matches what I just chose.
6. As a power user, I want the bowtie in that list, so that I can see a Failure
   with a reason and the input footprint drawn, not a blank page.
7. As a power user, I want the courtyard in that list, so that I can see a hole
   roofed without having to enter an inner ring by hand.
8. As a power user, I want the gabled rectangle in that list, so that I can see
   a verge without inventing a pitch list.

**Editing geometry**

9. As a power user, I want an optional table of outer-ring vertices `(x, y)` in
   metres, so that I can tweak a preset or try a footprint that is not in the
   corpus.
10. As a power user, I want an optional table for one hole's vertices, so that
    I can edit a courtyard-like plan without a drawing tool.
11. As a power user, I want to add or remove vertex rows and then submit, so
    that the edge count can change. (A few lines of script to add or remove
    rows is fine; the submit is still a form POST.)
12. As a power user, I want changing the vertex tables to rebuild the per-edge
    pitch rows (outer edges, then hole edges), so that I cannot submit a pitch
    list of the wrong length by accident.
13. As a power user, I want each pitch row labelled with its edge index and
    `from → to` coordinates, so that I know which wall I am editing.
14. As a developer, I want more than one hole to be out of this page, so that
    the form stays a form and not a CAD tool.

**Pitch, gable, overhang**

15. As a power user, I want one "apply to all" pitch control, so that I can set
    every edge to 45° (or `4:12`, or `100%`) in one action and then gable a
    single wall.
16. As a power user, I want each edge's pitch as a text field that accepts the
    same spellings `roof` already accepts, so that I am not learning a second
    language for slope.
17. As a power user, I want a gable checkbox on each edge that writes `90` and
    disables that row's pitch field, so that I do not have to remember that a
    gable is a vertical face.
18. As a power user, I want an overhang in metres, so that I can push the eaves
    out from the walls the way a real roof does.
19. As a power user, I want the plan and the 3D view to draw the original walls
    separately from the eaves when overhang is not zero, so that I can see the
    projection rather than a larger building.

**Reading the result**

20. As a power user, I want a describe block on every response, so that I get
    numbers and reasons in one place before I look at the drawings.
21. As a power user, I want a Failure to show `kind` and `reason`, so that I can
    fix the input instead of guessing.
22. As a power user, I want a Failure to draw the input footprint (and hole)
    and not a plan or a 3D solid, so that I am not shown a roof that does not
    exist.
23. As a power user, I want a Roof to show whether it is a terrain, the ridge
    height in metres, the total sloped area in m², and linear metres grouped by
    eave, hip, valley, ridge and verge, so that I can read the same quantities
    the notebooks print.
24. As a power user, I want a Roof that is not a terrain to still show the plan
    and the validity reasons, and not the 3D solid, so that I never orbit
    geometry the library has already rejected.
25. As a power user, I want a terrain Roof to show the plan (arcs coloured by
    kind, node heights annotated) and then an orbitable 3D solid, so that I can
    read the layout and then judge the massing.
26. As a power user, I want metres and degrees on the page, so that I never
    have to wonder about units.

**Trusting it**

27. As a power user, I want submitting the 10 × 6 m rectangle at 45° to report
    a 4 m ridge at height 3 m, so that I can check the page against the worked
    example I already trust.
28. As a power user, I want a self-intersecting footprint to come back as a
    Failure with kind `self_intersection`, so that I see the same refusal the
    library gives in Python.
29. As a power user, I want an unreadable pitch spelling to come back as a
    Failure with kind `invalid_pitch`, so that the form does not crash.
30. As a power user, I want a documented non-terrain footprint (for example a
    plus-shape, or an extra vertex on a straight wall) posted through the
    coordinate editor to show the plan, the validity reasons, and no 3D, so
    that the third result path is visible.
31. As a developer, I want nothing the form accepts to raise out of the
    request, so that a bad POST is a page with a Failure (or a validation
    note), not a 500.

**How the page is built**

32. As a developer, I want the HTML of the form to be in a template I can read,
    so that I learn how a webpage posts fields.
33. As a developer, I want the server to call `roof` and the existing plan and
    solid views, so that the engine is unchanged.
34. As a developer, I want the core package to remain free of web frameworks
    and of I/O, so that ADR-0001's exit (wrap CGAL later) stays cheap.
35. As a developer, I want Plotly.js loaded from a CDN and figures embedded as
    fragments, so that a page view does not ship a multi-megabyte inline
    bundle from our server.
36. As a developer, I want a `web` extra that pulls in Flask, Jinja, and the
    viz dependencies, so that `import krovlab` still has no third-party
    dependencies.
37. As a developer, I want a Dockerfile that runs this process on Python 3.13,
    binds `0.0.0.0`, and honours `PORT`, so that the same app can go to Cloud
    Run when a URL is needed.
38. As a developer, I want that Cloud Run service to scale to zero, stay
    unauthenticated, and live in `europe-west1`, so that idle cost is ~€0 and
    the recipient is not waiting on a US region.
39. As a developer, I want no login, no database, and no session, so that the
    page is one process and a form.

## Implementation Decisions

**One new seam, above the existing one.** The library seam stays `roof(...) ->
Roof | Failure`. The web feature adds exactly one seam on top: an HTTP
round-trip that takes form fields and returns the HTML page. Tests hit that
round-trip. They do not open the event queue, and they do not assert on CSS.

**Flask and a Jinja template, one route for GET and POST.** GET with no
submission shows the default rectangle already run. POST rebuilds the page
from the posted fields. There is no JSON API and no `fetch`. A few lines of
page script may add or remove table rows and copy "apply to all" into the
pitch fields; submit remains a form POST.

**Presets are the corpus, not a second geometry list.** The dropdown is the
committed footprint fixtures (by name). Choosing one loads that fixture's
rings, pitch, and overhang into the form. The page does not keep a hand-copied
parallel set of coordinates.

**The posted pitch list is the source of truth.** "Apply to all" fills every
edge row. A checked gable writes `90` on that edge. The server passes the
resulting list to `roof` as `pitch`, with the posted rings as `footprint` /
`holes` and the posted overhang. Spellings are whatever `roof` already parses.

**Three result branches, copied from the notebooks.**

| `roof` returns | Describe | Drawing |
|---|---|---|
| `Failure` | `kind` and `reason` | Input footprint (and hole) only |
| `Roof` and not a terrain | terrain flag, quantities, `validity.reasons` | Plan only |
| `Roof` and a terrain | terrain flag, quantities | Plan, then 3D solid |

The footprint-on-Failure drawing is a small Plotly figure owned by the web
app. It is not added to the viz module in this slice.

**Overhang uses the viz `walls` contract.** `roof(..., overhang=...)` first;
`plan_view` / `solid_view` get the original rings as `walls` and
`wall_holes` when overhang is not zero.

**Figures are fragments, not `write_html` files.** `write_html` inlines
Plotly.js for a disk file that opens over `file://`. This page is served over
HTTP, so Plotly.js comes from a CDN once per page and each figure is
`to_html` with Plotly omitted.

**A `web` extra, a Flask app outside the core package.** Artifact homes:
the application and its templates live under `web/` at the repo root; a
`Dockerfile` at the repo root builds that app; a short "Web demo" section is
added to `README.md`; this spec lives at `.scratch/roof-web-ui/PRD.md`; the
wrap decision is `docs/adr/0002-python-form-server-wraps-the-core.md`. None of
these paths is gitignored.

**Hosting is Cloud Run, after localhost works.** `min instances = 0`,
unauthenticated, `europe-west1`, Python 3.13 base image. No custom domain in
this slice.

## Testing Decisions

**A good test here asserts what the power user sees after a GET or POST, not
how Flask is wired.** Status code, which describe lines are present, which of
the three drawing branches rendered, and the worked-example numbers. A test
that matches CSS classes, template filenames, or Plotly trace ids is testing
the thing most likely to be restyled.

**The seam is the HTTP round-trip.** Use Flask's test client against the app.
Prior art for "the figure built, not pixels" is the viz smoke tests
(`test_plan_view_builds_from_a_roof`, `test_solid_view_builds_from_a_roof`,
`test_write_html_inlines_plotly`). Prior art for worked numbers is the roof
tests on the 10 × 6 m rectangle at 45° (4 m ridge at height 3 m) and the
gabled-rectangle pitch list. Prior art for named footprints is the corpus
loader and fixtures (`rectangle-10x6`, `l-shape`, `u-shape`, `courtyard`,
`rectangle-gabled`, `bowtie`, …). Prior art for Failure kinds is the roof
entry-point tests that assert `self_intersection` and `invalid_pitch`.

**Required HTTP cases**

- GET: 200, describe and both views for the default 10 × 6 m rectangle at 45°,
  ridge height 3 m, total sloped area matching the library.
- POST of the bowtie fixture: Failure `self_intersection`, footprint drawing
  present, no 3D solid.
- POST of the gabled-rectangle fixture: a terrain Roof, plan contains a verge,
  3D present.
- POST of the courtyard fixture: a terrain Roof, 3D present.
- POST with an unreadable pitch: Failure `invalid_pitch`, no 500.
- POST of a documented non-terrain footprint (plus-shape, or a collinear extra
  vertex — the cases in the limitations note): plan present, validity reasons
  present, no 3D solid.
- POST with overhang on the rectangle: 200, and the views are asked to
  distinguish walls from eaves (assert via the same `walls=` contract the viz
  tests already cover, or via the response still being a terrain Roof of the
  enlarged footprint).

Do not re-assert the terrain invariants; the library tests already own those.
Do not require a live Cloud Run project in CI. A Dockerfile that builds is
enough of a hosting check if it is cheap; if it is not cheap, document the
deploy command and skip it in pytest.

## Out of Scope

A JavaScript SPA, a JSON API, FastAPI, Streamlit, Gradio, Dash, Pyodide, and
any port of the skeleton out of Python.

A drawing canvas. Multiple holes in the editor. Per-edge pitch as a map
widget. Wavefront views and event stepping. Takeoff as a priced table or a
spreadsheet export — the describe block is the quantity readout for this
page.

Auth, accounts, saved designs, a database, rate limiting, a custom domain.

Adding `footprint_outline` to the viz module. Changing `roof`, the skeleton,
or the Failure taxonomy.

Cost optimisation, additive weights, and everything else in
`docs/future-work.md` except the web application, which this spec starts.

## Story coverage

| Stories | Ticket |
|---|---|
| 2–8, 20–23, 25–28, 32–36, 39; 5 starts (preset loads the fixture) | 01 default page and corpus dropdown |
| 15, 16, 17, 18, 19 | 02 per-edge pitch, gable, overhang |
| 9–14, 24, 29, 30, 31; 5 finishes (tables fill) | 03 coordinate editor and non-terrain |
| 1, 37, 38 | 04 Cloud Run container |

## Further Notes

**The risk is teaching the wrong lesson.** If the page is implemented as a
Plotly Dash or Streamlit app, the power user still sees a roof and the author
learns nothing about forms. The HTML template is a deliverable.

**Idle hosting should stay ~€0 without embarrassing the recipient.** That is
why Cloud Run won over Render Free (long wake) and why Plotly.js is not
inlined (egress). Keep `min instances = 0`.

**Non-terrain is a first-class branch, not an afterthought.** The corpus today
is almost all valid terrains plus one unroofable bowtie. The plus-shape /
collinear-vertex path must still be reachable from the optional coordinate
editor and covered by a test, or the page will look like the library never
fails that way.
