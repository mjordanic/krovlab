# 01: Centered apex and a typed offset

**What to build:** An experimental roof starts with the apex at the midpoint of the maximum-clearance set, the points inside the footprint farthest from the nearest wall. On the 10×6 rectangle that point is (5, 3). The roof is an apex: the faces meet at one point, and the takeoff has no ridge. At roof height 3 m the long walls are 45° and the short walls take a 3 m rise over a 5 m run. The same midpoint is the start on every experimental footprint, including the L.

The visitor types an offset in metres from that midpoint and clicks Update roof. The apex moves, the one roof height stays, and the pitches change. "Move" adds to the current offset. "Place at the center" sets it back to (0, 0). "1 m toward Wall N" moves 1 m toward that wall, perpendicular to it, using the page's Wall 1 numbering. On the rectangle, Wall 2 runs from (10, 0) to (10, 6), and 1 m toward it from the center is (6, 3). An offset that will not lift is pulled back along the line from the midpoint to the last place that still returns a roof. The fields show that offset, and Update again leaves the roof there.

Update keeps the offset. Changing roof height or editing a corner keeps it, measured from the new midpoint. An overhang keeps it from the midpoint of the enlarged footprint. Another example, or a DXF, returns to (0, 0). The skeleton ignores the fields. Switching back to experimental still has them. A single plane and a Failure show no placement controls. The face graph is unchanged. The page explanation says the visitor can move the apex. The helper learns these fields in 04.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Stories:** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 20, 27, 28, 49, 50, 51, 53, 54, 57, 68, 69, 70, 72, 73, 74

**Prior art:** `test_omitted_roof_height_rises_like_a_45_degree_hip_on_the_10_by_6`, `test_roof_height_sets_the_rise_above_the_eaves`, `test_overhang_puts_the_eaves_outside_the_walls`, `test_eave_height_shifts_the_roof_by_that_height`, `test_experimental_page_sets_roof_height_in_metres`, `test_switching_back_to_the_skeleton_restores_the_skeleton_roof`. ADR-0004. Glossary terms footprint, wall, pitch, face, ridge, eave, overhang, eave height, Failure.

**Artifact homes:** No new file. Placement is an optional argument of the experimental entry point. The offset fields and the experimental explanation live on the existing form page.

- [ ] An omitted placement on the 10×6 rectangle puts the apex at (5, 3) when the roof height is 3 m, with no ridge, long-wall pitch 45°, and the short-wall pitch a 3 m rise over a 5 m run
- [ ] The existing 3 m rise test on that rectangle still passes
- [ ] Offset (1, 0) puts the apex at (6, 3). Place-at-center returns it to (5, 3). A move adds to the current offset
- [ ] 1 m toward Wall 2 from the center of that rectangle puts the apex at (6, 3)
- [ ] An offset that leaves the footprint returns a Roof on the segment from the midpoint to the request, the fields show the offset that was used, and submitting that offset again returns the same interior
- [ ] Update, a roof-height change, and a corner edit keep the offset, measured from the current midpoint. Overhang is applied before the midpoint. Eave height lifts the finished roof
- [ ] Another example or a DXF resets the offset to (0, 0). A skeleton POST does not use the offset. The fields are still there after switching back to experimental
- [ ] A single plane and a Failure show no placement controls. The face graph is otherwise unchanged, and a supplied face graph still says which walls share a face
- [ ] The experimental explanation says the visitor can move the apex
- [ ] `roof` and `project` are unchanged. `import krovlab` still loads no experimental module and no PyTorch
