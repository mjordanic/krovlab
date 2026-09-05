# 03: Per-edge pitch, gable, and overhang

**What to build:** On the selected footprint, the power user sets slope the way
`roof` already understands it. One "apply to all" control fills every edge.
Each edge then has a text pitch (`45`, `4:12`, `100%`, `90`, …) labelled with
its index and `from → to`. A gable checkbox writes `90` and disables that row.
Overhang is metres; `roof` gets it as `overhang`, and when it is not zero the
plan and 3D receive the original rings as `walls` / `wall_holes` so the building
stays distinct from the eaves.

The posted pitch list is the source of truth. Submit is still a form POST.

**Blocked by:** 02

**Status:** ready-for-agent

**Stories:** 15, 16, 17, 18, 19

**Prior art:** `roof` pitch spellings (degrees, rise:run, percent) and
`pitch = 90` as a gable (ADR-0001, roof entry point). Gabled-rectangle fixture
pitch list `[45, 90, 45, 45]`. Overhang as an offset; viz `plan_view` /
`solid_view` `walls=` / `wall_holes=` contract and the viz tests that cover it.
PRD "The posted pitch list is the source of truth" and "Overhang uses the viz
walls contract."

- [ ] Apply-to-all fills every edge pitch row, then a single gable can be checked
- [ ] Each edge row shows index and `from → to`, and accepts `roof`'s pitch spellings
- [ ] A gable checkbox writes `90` and disables that row's pitch field
- [ ] Overhang posts through to `roof`; when non-zero, views get the original rings as walls
- [ ] POST of the rectangle with overhang 0.5 m returns 200 and a terrain Roof of the enlarged footprint
- [ ] Flask test client covers apply-to-all, a gable on one rectangle edge, and overhang
