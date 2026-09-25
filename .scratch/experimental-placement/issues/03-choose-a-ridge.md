# 03: Choose a ridge

**What to build:** Where the maximum-clearance set is a single segment and no face spans several walls, the form offers Apex and Ridge. Apex stays the default. On the 10×6 rectangle, Ridge at offset (0, 0) and roof height 3 m is the horizontal segment from (3, 3) to (7, 3). Every pitch is 45°. The takeoff includes that ridge. Apex on the same walls still has no ridge. The segment keeps its length and direction. The offset slides it, so the ridge midpoint sits where the apex sat. Switching between Apex and Ridge keeps the offset. The interior handle from the drag ticket slides the segment the same way it slides the apex.

An L, and a face that spans several walls, have no Ridge control. Asking for a ridge there leaves the apex and says so. A corner edit that removes the single segment drops the style back to Apex and keeps the offset. A corner edit that keeps the segment keeps the style and the offset. Another example resets to Apex. "Pyramid" and "pyramide" select Apex.

The page explanation says the visitor can move the apex and, where Ridge is offered, choose it. The helper learns Apex, Ridge, and the pyramid alias in 04.

**Blocked by:** 01: Centered apex and a typed offset, 02: Drag and snap the apex

**Status:** ready-for-agent

**Stories:** 15, 17, 18, 19, 21, 22, 23, 24, 25, 55, 60, 67, 71

**Prior art:** `test_terrain_quantities_use_the_same_definitions_as_roof`, `test_l_with_two_non_collinear_walls_on_one_face_returns_that_face`, `test_experimental_dropdown_lists_footprints_the_method_can_roof`, `test_catalog_example_roofs_under_either_method`. Glossary term ridge. ADR-0004, pitch stays off this path.

**Artifact homes:** No new file. The Apex / Ridge choice is a field of the existing form and an optional placement on the experimental entry point.

- [ ] The rectangle offers Apex and Ridge. Apex is selected on arrival. Ridge at offset (0, 0) and roof height 3 m is the segment (3, 3)–(7, 3), every pitch is 45°, and the takeoff includes that ridge
- [ ] Apex on that rectangle still has no ridge, and both roofs are terrains with the usual quantities
- [ ] Switching style keeps the offset. The offset slides the ridge without changing its length or direction. The interior handle drags the segment
- [ ] The L, and a face that spans several walls, offer no Ridge control
- [ ] A corner edit that removes the single clearance segment returns to Apex and keeps the offset. A corner edit that keeps the segment keeps the style
- [ ] The experimental explanation says the visitor can move the apex and, on the rectangle, choose a ridge
