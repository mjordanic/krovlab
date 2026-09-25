# 04: Hold a reflection

**What to build:** Each reflection the footprint actually has is a checkbox. The rectangle has two, and both start checked at offset (0, 0). Checking one removes only the part of the offset that breaks that reflection, and submits. Dragging off that axis clears that checkbox and keeps the new offset. The page says which of those reflections the current offset still lies on. A footprint with one reflection gets one checkbox. An L gets none.

"Make it symmetric" checks every reflection this footprint has. A symmetry the footprint lacks is a note, and the roof stays. A corner edit that removes a reflection removes that checkbox.

Update keeps the style, the offset, the checkboxes, and snap. Another example, or a DXF, resets to Apex, offset (0, 0), snap on, and every reflection of the new footprint checked. Switching to the skeleton ignores the placement. Switching back in the same visit restores the style, the offset, the checkboxes, and snap.

The helper is taught here, once the fields exist. It writes the same placement fields the form uses, and the reply tells the visitor to click Update roof. It can center, add an offset, move toward a Wall N, switch Apex and Ridge, turn snap on or off, and check symmetry boxes. Pyramid and pyramide mean Apex. Its instructions name that whole set, and they name the cases where a control is absent: no ridge on an L or a spanned face, no symmetry the footprint lacks, nothing to place on a single plane or a Failure. Those requests, and any other placement sentence, leave the fields unchanged and say so. Roof height, overhang, and eave height still work. Pitch and wall type are still refused while experimental is selected.

**Blocked by:** 02: Drag and snap the apex, 03: Choose a ridge

**Status:** done

**Stories:** 16, 26, 29, 30, 31, 32, 33, 34, 35, 36, 37, 52, 56, 58, 59, 61, 62, 63, 64, 65, 66, 75, 76

**Prior art:** `test_switching_back_to_the_skeleton_restores_the_skeleton_roof`, `test_skeleton_post_of_the_rectangle_still_matches_today`, `test_set_cell_roof_height_patches_the_experimental_form`, `test_help_prefers_the_skeleton_and_knows_the_graph_network`, `test_system_prompt_carries_glossary_limits_and_readme`. ADR-0003, the helper fills fields and the visitor clicks Update roof.

**Artifact homes:** No new file. The checkboxes are fields of the existing form. The helper's instructions live in its existing system prompt.

- [x] The rectangle shows two symmetry checkboxes, both checked at offset (0, 0). Checking one zeros only the component that breaks that reflection
- [x] Dragging off one axis clears that checkbox and keeps the offset. The page says which reflections the current offset still lies on
- [x] A footprint with one reflection shows one checkbox. The L shows none. Asking for a symmetry the footprint lacks changes nothing
- [x] "Make it symmetric" checks every reflection this footprint has
- [x] A corner edit that removes a reflection removes that checkbox
- [x] Update keeps the style, the offset, the checkboxes, and snap. A new example or a DXF resets to Apex, (0, 0), snap on, and every reflection of the new footprint checked
- [x] A skeleton POST ignores the placement. Switching back to experimental restores the style, the offset, the checkboxes, and snap
- [x] The helper can center, add an offset, move toward a wall, switch Apex and Ridge, set snap, and check symmetry. Pyramid and pyramide select Apex. The reply tells the visitor to click Update roof
- [x] A ridge on an L or a spanned face, a symmetry the footprint lacks, a placement when there is no interior, and an unknown placement sentence patch nothing
- [x] The helper still sets roof height, overhang, and eave height, and still refuses a wall type while experimental is selected
- [x] The helper's instructions name the apex, the ridge, the offset, a move toward a wall, snap, and symmetry, and they name the cases where a control is absent
