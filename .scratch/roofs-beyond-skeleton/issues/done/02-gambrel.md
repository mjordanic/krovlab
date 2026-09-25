# 02: Gambrel

**Prerequisite:** Same as ticket 01 — project-from-cells already on the branch.

**What to build:** The architect gives an edge a steep pitch, a shallow pitch,
and a break height in metres above that cell's eave. The takeoff reports two
faces on that wall (steep then shallow). A barn break is those three numbers on
that wall.

One story per edge: gambrel plus knee, and gambrel plus gable, are named
failures. Click the edge to set the gambrel, or type it in the millimetre table.
Submit is still POST.

**Blocked by:** 01 knee height

**Status:** done

**Complexity:** high

**Stories:** 6, 7, 8, 9, 10, 26 (finishes: click edge for gambrel)

**Prior art:** Feature PRD "One story per edge" and the gambrel worked example in
Testing Decisions (60° then 30° on the long walls, known break). Ticket 01 owns
knee and gable-plus-knee; this ticket owns the remaining combinations. Pitch
spellings already accepted by `roof`. Form POST; Flask test client.

- [x] Rectangle, long edges gambrel 60° then 30° at a known break: two faces per
      long wall, plan areas sum to the footprint, sloped area is the sum of the
      two bands
- [x] Break height is metres above that cell's eave, not a paper delay unit
- [x] Gambrel plus knee on the same edge is a named Failure
- [x] Gambrel plus gable on the same edge is a named Failure
- [x] POST of those three numbers on an edge matches a cell with that gambrel
- [x] Where there is no dormer, the result remains a terrain: plan-area,
      planarity, and drainage-to-own-eave still hold
