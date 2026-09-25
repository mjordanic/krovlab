# PRD: Place the experimental apex or ridge

Status: ready-for-agent

Vocabulary in this document is defined in `CONTEXT.md`. Terms are used in their
glossary sense — footprint, wall, pitch, roof, face, ridge, hip, eave,
overhang, eave height, terrain, takeoff, Failure — and not loosely. Do not
call the footprint an outline. Respects ADR-0001 (the weighted straight
skeleton stays the core), ADR-0002 (the form server wraps the core),
ADR-0003 (the helper fills form fields and the visitor clicks Update roof),
and ADR-0004 (the experimental method stays optional, unpitched, and outside
`roof` / `project`).

The page label **Apex** means the single interior point where the faces of
the experimental roof meet. The glossary has no separate word for that point.
**Ridge** is the glossary term.

## Problem Statement

On the experimental path, a 10×6 m rectangle comes back as a pyramid whose
tip sits near one end of the footprint, about (3, 3), rather than over the
middle, (5, 3). The roof is symmetric about the long axis and not about the
short axis. A visitor who wants the usual symmetric roof cannot move that
tip, and a visitor who wants it somewhere else cannot say so either.

The face-adjacency network only decides which walls share a face. It does
not choose where the interior sits. Two roofs with the same faces can put
that interior in different places. Training the network again cannot tell
those roofs apart.

The visitor needs to choose. Centered and symmetric is the usual start.
It is a preference, not a rule. The same visit must be able to slide the
interior off center, keep one reflection and drop the other, or ask for a
horizontal ridge instead of a point.

## Solution

The experimental roof still starts from the network's face graph, then lifts
it. The usual lift puts an apex at the midpoint of the maximum-clearance
set: the points inside the footprint farthest from the nearest wall. On the
10×6 rectangle that midpoint is (5, 3). The visitor can leave it there or
move it.

Where it sits is an offset, in metres, from that midpoint. Dragging the
interior of the plan, typing the offset, and the helper all write that same
offset. The walls stay where they are. One roof height remains the only
vertical measure. Sliding the interior changes pitches.

On a footprint whose maximum-clearance set is one segment, and whose faces
do not span several walls, the visitor can choose **Ridge** instead of
**Apex**. The ridge is that segment, at its own length and direction.
Choosing it does not become the default. The offset then slides the
segment. On the rectangle the segment runs from (3, 3) to (7, 3).

Each reflection the footprint actually has gets a checkbox. Checking it
holds the interior on that axis. Dragging off the axis clears that
checkbox. A footprint with no reflection gets no checkbox.

A drag that will not lift stops at the last place along the way that still
returns a roof. The fields show the offset that was used. The drawing stays.

## User Stories

1. As a visitor who opens the experimental rectangle, I want the apex over the middle of the footprint, so that the roof is symmetric before I touch anything.
2. As a visitor on that rectangle, I want the default roof to be an apex, with the faces meeting at one point, so that I am looking at the same kind of roof as before, only centered.
3. As a visitor, I want a centered roof to be the usual start on every experimental footprint, so that I begin from the placement people usually prefer.
4. As a visitor, I want to move the apex away from that middle, so that symmetry is a choice I can leave.
5. As a visitor, I want to put the apex back in the middle after I have moved it, so that I can return to the usual placement.
6. As a visitor on an L, I want the apex at the midpoint of the maximum-clearance set, so that "middle" means the same thing as on the rectangle and does not pretend the L has a reflection.
7. As a visitor, I want the offset stored as metres from that midpoint, in the footprint's own axes, so that (0, 0) means centered and a typed pair means a definite move.
8. As a visitor, I want "move" to shift the offset I already have, so that a second nudge adds to the first.
9. As a visitor, I want "place at the center" to set the offset back to (0, 0), so that centering does not depend on where the apex sits now.
10. As a visitor, I want "1 m toward Wall N" to move the interior 1 m toward that wall, perpendicular to it, so that I can talk about walls the way the page numbers them.
11. As a visitor, I want Wall N to be the same number I see on the page, starting at Wall 1, so that the helper and the form mean the same wall.
12. As a visitor, I want one roof height to stay the height of the interior, so that I still have a single vertical measure.
13. As a visitor who slides the apex toward a wall, I want the pitches to change, so that the faces still meet at the height I set.
14. As a visitor on the 10×6 rectangle with roof height 3 m and offset (0, 0), I want the long walls at 45° and the short walls at the pitch of a 3 m rise over a 5 m run, so that I can see the centered apex is not an equal-pitch hip.
15. As a visitor, I want a control labelled Apex and Ridge, so that the words on the form match the glossary where it has a word.
16. As a visitor who says "pyramid" or "pyramide" to the helper, I want Apex selected, so that the word I use still hits the control.
17. As a visitor on the rectangle, I want to choose Ridge and get the segment from (3, 3) to (7, 3) when the offset is (0, 0), so that I can have the equal-pitch hip with a real ridge.
18. As a visitor who chooses Ridge at roof height 3 m and offset (0, 0) on that rectangle, I want every face at 45°, so that the ridge is the equal-pitch hip and not the pyramid.
19. As a visitor who chooses Ridge, I want the takeoff to include that ridge, so that the line I see is a quantity.
20. As a visitor who stays on Apex, I want no ridge in the takeoff, so that a point is not reported as a ridge.
21. As a visitor, I want Ridge to keep the segment's length and direction, so that this control does not rotate the ridge or shorten it.
22. As a visitor, I want the offset to slide the ridge, so that its midpoint sits where the apex sat.
23. As a visitor who switches between Apex and Ridge, I want the offset kept, so that where it sits and whether it is a point or a ridge are separate choices.
24. As a visitor on an L, I want no Ridge control, so that I am not offered a single ridge the footprint does not have.
25. As a visitor whose face spans several walls, I want no Ridge control, so that a spanned face stays an apex I can move.
26. As a visitor who asks the helper for a ridge when the control is absent, I want a short note and the apex left as it is, so that the request does not invent a ridge.
27. As a visitor on a single-plane roof, I want the placement controls hidden, so that I am not asked to move an interior the roof does not have.
28. As a visitor whose experimental result is a Failure, I want the placement controls hidden, so that there is nothing to drag on an empty drawing.
29. As a visitor who asks the helper to place an interior when there is none, I want a note and no change, so that the helper does not invent a point.
30. As a visitor on the rectangle, I want two symmetry checkboxes, one for each reflection, so that I can hold the long axis, the short axis, or both.
31. As a visitor at offset (0, 0), I want every available symmetry checkbox checked, so that the usual start shows the symmetries it has.
32. As a visitor, I want checking one reflection to remove only the part of the offset that breaks it, so that I can slide along the other axis.
33. As a visitor, I want dragging off one axis to clear that checkbox and keep the new offset, so that the latest move wins.
34. As a visitor on a footprint with one reflection, I want one checkbox, so that the form only offers a symmetry the walls have.
35. As a visitor on an L, I want no symmetry checkbox, so that the form does not offer a symmetry the L lacks.
36. As a visitor who asks for a symmetry the footprint lacks, I want a note and the roof left alone, so that the drawing is not cleared.
37. As a visitor, I want the page to say which of the footprint's reflections the current offset still lies on, so that I can see what the checkboxes are holding.
38. As a visitor, I want to drag a footprint corner and edit the walls as I do today, so that the new handle does not take away the plan editor.
39. As a visitor, I want a separate interior handle for the apex or the ridge, so that grabbing a corner never moves the interior and grabbing the interior never moves a corner.
40. As a visitor, I want the handle to follow the pointer while I drag, and the offset numbers to follow it, so that I can see where I am before the roof rebuilds.
41. As a visitor, I want snap to a 0.5 m grid on when I load an example, so that a drag lands on a coarse building grid.
42. As a visitor with snap on, I want the grid measured from the plan origin in the footprint's coordinates, so that the grid matches the metre axes of the drawing.
43. As a visitor with snap on, I want the clearance midpoint, and a symmetry axis, to win when the pointer is within 0.25 m of them, so that the middle is easy to hit when it does not lie on a grid point.
44. As a visitor, I want a snap control that turns the grid off, so that I can drag to an exact point.
45. As a visitor with snap off, I want the handle to follow the pointer exactly, so that the center magnets belong to snap and not to every drag.
46. As a visitor, I want pointer-up to submit the form the way Update roof does, so that the plan and the 3D rebuild from the offset I released on.
47. As a visitor, I want snap to stay as I set it across Update on the same building, so that I do not have to turn it off again after every rebuild.
48. As a visitor who loads another example or a new footprint, I want snap on again, so that a new building starts from the usual settings.
49. As a visitor who types an offset the lift cannot build, I want the interior pulled back along the line from the midpoint to the last place that still returns a roof, so that I keep a drawing.
50. As a visitor, I want the offset fields to show the place that was used after a pull-back, so that the numbers match the roof.
51. As a visitor who updates again after a pull-back, I want the same roof, so that the clamped offset is stable.
52. As a visitor, I want Update to keep the style, the offset, the symmetry checkboxes, and snap, so that a rebuild does not forget the placement.
53. As a visitor who changes roof height, I want the offset kept, so that a taller roof stays where I put it in plan.
54. As a visitor who changes overhang, I want the same offset from the midpoint of the enlarged footprint, so that "1 m from the middle" still means that after the eaves grow.
55. As a visitor who edits a corner of the current footprint, I want the style and the offset kept and reapplied from the new midpoint, so that nudging a wall is not a new building.
56. As a visitor who loads another example, a DXF, or otherwise replaces the footprint, I want Apex, offset (0, 0), snap on, and every reflection of the new footprint checked, so that a new building starts from the usual placement.
57. As a visitor who switches to the skeleton, I want today's skeleton roof, so that the placement fields do not move a skeleton ridge.
58. As a visitor who switches back to experimental in the same visit, I want the style, offset, checkboxes, and snap restored, so that the experimental placement is still there.
59. As a visitor whose corner edit removes a reflection, I want that checkbox to disappear, so that I cannot lock a symmetry the walls no longer have.
60. As a visitor whose corner edit removes the single clearance segment, I want Ridge to drop back to Apex and the offset kept, so that a style the footprint can no longer offer does not stay selected.
61. As a visitor using the helper, I want it to write the same placement fields the form uses, so that a sentence and a drag cannot disagree.
62. As a visitor using the helper, I want the reply to tell me to click Update roof, so that the helper behaves as it does for roof height.
63. As a visitor, I want the helper to center, to move by an offset, to move toward a wall, to switch Apex and Ridge, to set snap, and to turn on symmetry checkboxes, so that I can ask for the placements the form can already express.
64. As a visitor who says "make it symmetric", I want every reflection of this footprint checked, so that one sentence holds every symmetry the walls have.
65. As a visitor who asks the helper for something it cannot place, I want a note and no change to the fields, so that an unknown instruction does not guess a roof.
66. As a visitor, I want the helper to keep setting roof height, overhang, and eave height, so that those knobs stay available on this path.
67. As a visitor, I want the experimental explanation to say that I can move the apex and, on the rectangle, choose a ridge, so that the new handles are visible before I hunt for them.
68. As a visitor, I want the face graph left as the network or the example set it, so that moving the interior does not merge or split faces.
69. As a visitor, I want a supplied face graph to still mean which walls share a face, so that placement is only where the interior sits.
70. As a visitor, I want overhang applied before the midpoint is measured, and eave height applied after the roof exists, so that those two knobs keep the meanings they have now.
71. As a visitor, I want a centered apex and a centered ridge on the rectangle to be terrains, with plan area, sloped area, and the usual line lengths, so that the takeoff still means what it means on any other roof.
72. As a maintainer, I want an omitted placement to mean the centered apex, so that existing callers get the usual start without a new argument.
73. As a maintainer, I want `roof` and `project` unchanged, so that the skeleton stays the core ADR-0001 and ADR-0004 describe.
74. As a maintainer, I want `import krovlab` to keep loading no experimental code and no PyTorch, so that a placement argument does not pull the network into the core.
75. As a maintainer, I want the helper to refuse pitch and wall type while experimental is selected, so that ADR-0003 and ADR-0004 still hold on this path.
76. As a visitor using the helper, I want its instructions to know about the apex, the ridge, the offset, snap, and symmetry, including when a control is absent, so that it offers those choices and does not invent a placement the form cannot express.

## Implementation Decisions

- The experimental entry point gains an optional placement. Omitted, it is Apex at offset (0, 0): the midpoint of the maximum-clearance set, the points inside the footprint whose distance to the nearest wall is greatest. On the rectangle (0, 0), (10, 0), (10, 6), (0, 6) that midpoint is (5, 3), and the set is the segment (3, 3)–(7, 3). This replaces the search that returned an end of that segment. Roof height, overhang, and eave height keep their order and their meanings. Pitch is still not an argument.
- The offset is `(dx, dy)` in metres in the footprint's axes, added to the midpoint. The apex is that point at the roof height. A multi-wall face still lifts its intermediate corners onto the plane through that apex, as it does today.
- Ridge is available only when the maximum-clearance set is a single segment and no face spans several walls. The ridge is that segment translated by the offset, at the roof height, horizontal, with the segment's length and direction. On the rectangle at roof height 3 m and offset (0, 0) the ridge is (3, 3)–(7, 3) and every pitch is 45°. The wall-face partition is unchanged: Ridge changes how those faces meet in the interior.
- Switching style keeps `(dx, dy)`. If a later edit of the walls makes Ridge unavailable, the style becomes Apex and the offset stays. Posting Ridge when it is unavailable leaves Apex.
- A reflection is an axis that maps the footprint onto itself. Each such axis is a checkbox. Checking it removes the component of the offset perpendicular to that axis and submits. At offset (0, 0) every such checkbox is checked. Dragging off an axis clears that checkbox. The page states, for each axis, whether the current offset lies on it. An L has none.
- "1 m toward Wall N" adds 1 m in the direction from the interior toward that wall, perpendicular to the wall, using the page's Wall 1 numbering. On the 10×6 rectangle, Wall 2 runs from (10, 0) to (10, 6), and 1 m toward it from the center is (6, 3). "Move" adds. "Place at the center" sets (0, 0).
- The plan editor keeps corner dragging. The interior handle is a different target. While the pointer is down the handle and the offset fields follow. Snap on quantizes to a 0.5 m grid from the plan origin, except the midpoint and a symmetry axis win when the pointer is within 0.25 m. Snap off follows the pointer. Pointer-up submits the form. Snap is a form field: it survives Update, and a replaced footprint turns it on.
- A requested interior that does not lift is pulled back along the segment from the midpoint to the request, to the last place that returns a roof. The fields then show that offset. Submitting it again returns the same roof. A graph that will not lift even at the midpoint stays the existing unliftable Failure, and the placement controls are absent. A single plane has no interior handle; the controls are absent there too.
- Placement fields stay in the form across a method switch. The skeleton does not read them. Switching back to experimental uses the fields still in the form. Replacing the footprint (another example, or a DXF) resets to Apex, (0, 0), snap on, and every reflection of the new footprint checked. Editing a corner of the current footprint keeps style and offset and measures the midpoint again.
- The helper writes these fields through the existing cell tool. It does not submit and does not rebuild the roof. The reply still tells the visitor to click Update roof. It can center, add an offset, move toward a wall, set Apex or Ridge, set snap, and check symmetry boxes. "Make it symmetric" checks every reflection this footprint has. Pyramid and pyramide mean Apex. A ridge request when Ridge is absent, a symmetry the footprint lacks, a placement when there is no interior, and any other placement sentence leave the fields unchanged and say so. Roof height, overhang, and eave height stay on that tool. The helper's own instructions name these options in the same words as the page, including when a control is absent, so the model offers them instead of inventing a placement.
- The experimental explanation on the page says the visitor can move the apex and, where Ridge is offered, choose it. The skeleton explanation is unchanged.
- The face-adjacency checkpoint is unchanged. No new weights, no new training, no condition vector.

## Testing Decisions

A good test calls the experimental entry point, posts the form, runs the plan editor, or runs the helper with an injected model, and asserts the roof or the fields that come back. It does not assert search steps, layer activations, or the text of a log line.

The geometry seam is the experimental entry point, the same seam the experimental roof tests already use. A footprint and an optional placement go in; a Roof or a Failure comes out.

- An omitted placement on the 10×6 rectangle puts the interior point at (5, 3) when the roof height is 3 m, with no ridge, the long-wall pitch 45°, and the short-wall pitch the rise over the 5 m run. The existing roof-height test that expects a 3 m rise on that rectangle still passes.
- Offset (1, 0) moves that point to (6, 3). Place-at-center returns it to (5, 3).
- Ridge at offset (0, 0) and roof height 3 m is the horizontal segment (3, 3)–(7, 3), every pitch 45°, and the takeoff includes a ridge. Apex at the same height includes none.
- Switching to Ridge keeps the offset. A footprint that is not a single clearance segment, and a face that spans several walls, stay on Apex.
- An offset that leaves the footprint comes back as a Roof whose interior lies on the segment from the midpoint to the request, and a second call with the offset the first call settled on returns the same interior.
- A single-plane graph has no interior point to move. An unliftable graph is still Failure `unliftable`. Overhang is applied before the midpoint; eave height shifts the finished roof. Pitch is still not an argument. `import krovlab` still does not load the experimental module.

The form seam is the existing form POST.

- The experimental rectangle page offers Apex and Ridge, the offset, snap on, and two symmetry checkboxes. The L offers Apex and the offset, and offers neither Ridge nor a symmetry checkbox. A single plane and a Failure offer none of them.
- Posting an offset changes the interior. Posting Ridge on the rectangle changes the roof to the segment above. Posting Ridge on the L leaves an apex.
- Checking one reflection zeros only the breaking component. Update keeps style, offset, checkboxes, and snap. Another example resets them. A skeleton POST of the rectangle still matches today's skeleton roof. Switching back to experimental uses the placement fields that remained in the form.
- The experimental explanation mentions moving the apex and choosing a ridge.

The drag seam is the plan editor, the same seam the plan-editor tests already use.

- Dragging the interior handle writes the offset and leaves the footprint corners where they are. Dragging a corner writes the corner and leaves the offset fields as they are. With snap on, a release near the midpoint writes (0, 0), and a release elsewhere writes a 0.5 m grid point. With snap off, the release writes the pointer's metres.

The helper seam is the injected-model turn, the same seam the help-agent tests already use.

- A turn that centers, moves toward Wall 2, selects Ridge, or checks symmetry patches those fields and tells the visitor to click Update roof. A ridge request on the L, and an unknown placement sentence, patch nothing. The helper still sets roof height on the experimental form and still refuses a wall type there. The helper's instructions name the apex, the ridge, the offset, snap, and symmetry, and they name the cases where a control is absent.

Prior art: the experimental roof tests that branch on Roof versus Failure, including the 10×6 roof-height test and the overhang and eave-height tests; the experimental form tests that POST the rectangle, the L, and a switch back to the skeleton; the plan-editor tests that move a vertex and read the posted fields; the help-agent tests that patch roof height through an injected model and refuse a wall type while experimental is selected.

## Out of Scope

- Retraining or conditioning the face-adjacency network. A learned prior over placement. Classifier-free guidance. A new checkpoint.
- Choosing the ridge's length, choosing its direction, or shortening it to a point.
- A ridge on a footprint whose maximum-clearance set is not one segment, including the L.
- A sloping ridge, a second roof height, or per-wall pitch on this path.
- Changing which walls share a face. Symmetry does not merge or split faces.
- The skeleton, its pitches, gables, knees, gambrels, holes, dormers, and extra cells.
- The helper rebuilding the roof itself, or submitting the form.
- A live rebuild of the solid while the pointer is still down.
- Publishing a separate literature essay. The reason placement is not a new network is the further note below.

## Further Notes

The off-center tip is an artifact of how the lift picks one point from a segment on which every point has the same clearance. Ren, Zhang, Wu, Huang, Fan, Ovsjanikov, and Wonka (ACM TOG 2021, arXiv:2109.07683) already split the work the same way: the network predicts face adjacency, and user intent is a regularizer and a drag on the embedding (their aesthetic energy and §6.4). They also report that one generator which tries to emit a finished roof fights the discrete graph and the continuous planarity at once (§6.3). This PRD follows that split. The network stays a face graph. The visitor's intent is the offset, the Apex/Ridge choice, and the reflection checkboxes.

An earlier note in the design conversation said a move toward a wall follows the wall's inward normal. The inward normal points into the footprint, away from the wall. The behavior in this PRD is the visitor's sentence: toward that wall, so the distance to it decreases.

The default apex moves. Callers who omit placement, including the rectangle example, get (5, 3) rather than the old end of the clearance segment. That change is the usual start this PRD exists to make.
