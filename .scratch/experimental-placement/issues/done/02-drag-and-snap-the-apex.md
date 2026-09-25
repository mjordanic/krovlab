# 02: Drag and snap the apex

**What to build:** The building plan gains an interior handle on the apex, separate from the footprint corners. Dragging a corner still edits that corner and leaves the offset as it is. Dragging the handle moves only the apex. While the pointer is down, the handle and the offset numbers follow it. Releasing submits the form the way Update roof does.

Snap to a 0.5 m grid is on for a newly loaded example. The grid is measured from the plan origin in the footprint's coordinates. The clearance midpoint, and a symmetry axis, win when the pointer is within 0.25 m of them. A snap control turns the grid off, and the handle then follows the pointer exactly. Snap survives Update on the same building. Another example, or a new footprint, turns it on again. The helper learns snap in 04.

**Blocked by:** 01: Centered apex and a typed offset

**Status:** done

**Stories:** 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48

**Prior art:** `test_editing_a_table_vertex_moves_it_on_the_plan`, `test_roof_height_round_trips_in_fields`. The plan editor's metre-space actions write the same fields the page POSTs.

**Artifact homes:** No new file. The handle and the snap control live in the existing plan editor. Snap is a field of the existing form.

- [x] Dragging the interior handle writes the offset and leaves the footprint corners where they are
- [x] Dragging a corner writes the corner and leaves the offset fields as they are
- [x] While the pointer is down, the handle and the offset numbers follow it. Pointer-up submits the form
- [x] With snap on, a release within 0.25 m of the midpoint writes (0, 0), and a release elsewhere writes a 0.5 m grid point measured from the plan origin
- [x] With snap off, the release writes the pointer's metres, including through the midpoint
- [x] Snap is on for a newly loaded example, survives Update, and turns on again when the example or the footprint is replaced
