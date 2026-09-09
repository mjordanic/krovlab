# 01: Knee height

**Prerequisite:** The project-from-cells feature is already on the branch
(cells, `project`, plan as editor). This folder's Blocked by lines are internal
only; do not start this ticket until that feature is done.

**What to build:** The architect sets a knee height on an edge in metres. The
wall stands vertical to that height, then the edge's pitch begins. Half-hip,
Dutch, and gablet are this one knob at different heights, plus a gable or a
small remaining hip as the pitch on that edge. Zero knee height is the same
roof as today. A gable (pitch 90) with a knee height is refused by name.

Internally this is an additive delay; the architect never sees a weight. Do not
ask them to draw a vertical strip as its own polygon. A knee on one edge of a
two-cell project affects only that cell.

On the page, click an edge and set knee height (millimetre table still works).
Submit is still POST. Existing cell drawing, eave heights, and project takeoff
keep working.

**Blocked by:** None (can start immediately once the prerequisite above holds)

**Status:** ready-for-agent

**Complexity:** high

**Stories:** 1, 2, 3, 4, 5, 26 (starts: click edge for knee; gambrel in 02), 29,
32, 33, 34, 35, 36, 37, 38

**Prior art:** Feature PRD "Knee is a delay, not a second cell" and "Architect
words on the seam; weights inside". ADR-0001 (additive weights reachable). Gable
is pitch 90. Ticket 01 of project-from-cells for assess-then-lift. Flask test
client; form POST. Worked example: rectangle, one short-edge knee equal to the
would-be full-hip ridge — that edge is a vertical gablet; neighbouring faces
close as verges above the knee; ridge height matches the un-kneed rectangle.

- [ ] Zero knee height on every edge equals today's roof of the same footprint
      and pitches
- [ ] Rectangle, one short-edge knee height equal to the full-hip ridge: that
      edge is a vertical gablet, neighbours close over it as verges above the
      knee, ridge height matches the un-kneed rectangle
- [ ] Pitch is still the public parameter; no weight appears on the cell or the
      returned roof
- [ ] Gable plus knee on the same edge is a named Failure
- [ ] A knee on one edge of a two-cell project leaves the other cell's roof
      unchanged
- [ ] POST of a knee height on an edge matches `project` of a cell with that
      knee; click-to-set is enough, tables still work
- [ ] Core still imports no Flask; Failure is a value; same input, same project
- [ ] A plus-shape POST still shows plan, validity reasons, and no 3D
