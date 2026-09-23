# 02: Choose the method, and roof one footprint from a face graph

**What to build:** The top of the page, above the example catalog, offers the standard skeleton or an experimental graph network. The skeleton is selected on arrival. Leaving it selected keeps today's page: pitch, gable, knee, gambrel, overhang, eave height, a hole, several cells, a dormer, the same plan, the same 3D solid, and the same Failure.

Choosing the experimental method shows that this path lifts a face graph into a planar roof and that pitch is not an input. Gable, knee, gambrel, holes, dormers, and extra cells are visibly not part of this method. The page does not roof them with the skeleton under the experimental label. It does not yet say a network chose the graph; that sentence arrives when the checkpoint is wired in.

The experimental entry point takes one footprint, an optional overhang, an optional eave height, and a face graph: which walls share a face, including one face over several non-collinear walls. It returns a Roof or a Failure. It does not take a pitch. Overhang offsets the footprint first. Eave height lifts every node after the roof exists. The same terrain check as any other Roof runs on the result. A terrain roof's plan area, sloped area, and eave, hip, valley, ridge, and verge lengths use the same definitions as the skeleton.

One L-shaped footprint is supplied with a face graph in which two non-collinear walls are one face. The page, given that footprint on the experimental path, shows its plan and its 3D solid. The skeleton on the same walls still has one face per wall. A supplied graph that cannot be lifted is Failure `unliftable`. A footprint with no supplied graph is Failure `no_face_graph`, not a crash and not a skeleton roof. Switching back to the skeleton restores the skeleton roof.

The glossary gains one sentence: a face of the skeleton rises from one wall; an experimental face may span several walls. An ADR records that the skeleton remains the default and the only core, and that this method is optional, unpitched, and outside that core. The help agent is unchanged.

**Blocked by:** None (can start immediately)

**Status:** done

**Stories:** 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 15, 17, 18, 19, 33, 34

**Prior art:** ADR-0001, ADR-0002, ADR-0003 (help agent stays as it is). The tests that call `roof` and branch on Roof versus Failure, including overhang and eave height. The tests that POST the form and read the returned page. `CONTEXT.md` **Face**. Worked numbers for the skeleton path stay the ones the form already shows (the 10 × 6 m rectangle at 45° has a 4 m ridge at height 3 m). PRD testing decisions: compare which faces meet, not coordinates alone.

**Artifact homes:** Glossary sentence in `CONTEXT.md`. ADR at `docs/adr/0004-experimental-method-is-optional.md`. Both are tracked paths.

- [x] Opening the page has the skeleton selected, and the choice sits above the example catalog
- [x] The two labels are the standard skeleton and an experimental graph network
- [x] A skeleton POST still matches today's roof, plan, 3D solid, and Failure, including pitch, gable, knee, gambrel, overhang, eave height, a hole, several cells, and a dormer
- [x] The experimental path says pitch is not an input, and gable, knee, gambrel, holes, dormers, and extra cells are visibly excluded
- [x] The experimental entry point does not take a pitch. It takes a footprint, an optional overhang, an optional eave height, and a face graph, and returns a Roof or a Failure
- [x] An L-shaped footprint whose supplied face graph covers two non-collinear walls with one face returns a Roof of that face structure, with plan and 3D on the page
- [x] The skeleton on that same L still has one face per wall
- [x] A terrain experimental roof reports validity, plan area, sloped area, and arc lengths by kind under the same definitions as `roof`
- [x] Overhang puts the eaves outside the walls. Eave height shifts the roof by that height
- [x] A graph that cannot be lifted is Failure `unliftable`. A footprint with no face graph is Failure `no_face_graph`
- [x] Switching back to the skeleton and submitting restores the skeleton roof
- [x] `CONTEXT.md` states that an experimental face may span several walls, and the skeleton's one-wall rule stays
- [x] ADR 0004 records that the skeleton remains the default core and this method is optional and unpitched
- [x] `import krovlab` still imports no third-party package. The help agent is unchanged
