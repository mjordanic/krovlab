# 04: Coordinate editor and the non-terrain branch

**What to build:** The power user can leave the corpus and type vertices. An
optional outer-ring table and an optional table for **one** hole (not N holes).
Adding or removing rows is allowed (a few lines of page script is fine); submit
stays a form POST. Changing vertices rebuilds the per-edge pitch rows — outer
edges, then hole edges — so a `pitch_count` Failure is not the normal way to
learn you added a point.

Picking a corpus name still fills these tables (story 5, finished here).

This ticket also closes the third result branch and the remaining refusals:
a documented non-terrain footprint (plus-shape, or an extra vertex on a
straight wall, as in the limitations note) posted through the editor shows the
plan, `validity.reasons`, and no 3D. An unreadable pitch spelling returns
`invalid_pitch`, not a 500. Nothing the form accepts raises out of the request.

**Blocked by:** 03

**Status:** ready-for-agent

**Stories:** 5 (tables filled from the preset), 9, 10, 11, 12, 13, 14, 24, 29, 30, 31

**Prior art:** `pitch_count` and `invalid_pitch` on the roof entry point.
Limitations note: plus-shaped plans, collinear extra vertices, mixed pitch on
some L-shapes — a `Roof` with `validity.is_terrain` false, not always a
`Failure`. Notebooks: non-terrain → plan only, print `validity.reasons`.
PRD "Required HTTP cases" for invalid pitch and non-terrain POST. One hole
only is an explicit out-of-scope for N holes, not a missing feature.

- [ ] Outer vertices and at most one hole can be edited as `(x, y)` metres and submitted
- [ ] Adding or removing vertices rebuilds pitch rows (outer then hole) before or as part of submit
- [ ] Pitch rows stay labelled with index and `from → to` after an edit
- [ ] Choosing a corpus fixture fills the coordinate tables and pitch rows
- [ ] POST of an unreadable pitch returns Failure `invalid_pitch` and not HTTP 500
- [ ] POST of a documented non-terrain footprint shows plan, validity reasons, and no 3D
- [ ] No accepted form POST raises out of the request
- [ ] Flask test client covers invalid pitch and one non-terrain case
