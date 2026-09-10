# 03: Wrap consecutive edges

> **Removed from the product.** Consecutive-edge wrap was taken out after
> the embedding produced a pierced 3D on the headline L and sent outer
> corners below the eave. Findings and options:
> [`docs/future-work.md`](../../../../docs/future-work.md) §6.

**Prerequisite:** Same as ticket 01 — project-from-cells already on the branch.

**What to build:** The architect marks consecutive edges of a cell as one plane.
That face wraps the corner with no hip. One pitch (or one gambrel) for the
merged face. A cell with no wrap groups is still the existing skeleton.

That cell is not run through the existing wavefront. It is embedded with a roof
graph in the sense of Ren et al. 2021: outline vertices, merged outline edges as
one face, planarity as the objective. If the embedding is not planar to the
existing planarity tolerance, return a Failure.

Refusals: non-consecutive edges; wrapped edges with disagreeing pitches. There
is no dual-graph editor and no public from-graph function. If this work seems to
need a third public function besides `roof` and `project`, stop and revisit the
spec.

On the page, select consecutive edges and choose "one plane". Submit is still
POST.

**Blocked by:** None (can start immediately once the prerequisite above holds)

**Status:** done

**Complexity:** high

**Stories:** 20, 21, 22, 23, 24, 25, 28

**Prior art:** Feature PRD wrap decisions and Testing Decisions L-shape example.
Ren et al. 2021 on faces with several outline edges. Existing planarity
tolerance used by validity. Gable mask and `project` of several cells remain
the ways to get other styles — wrap is the only graph edit. ADR-0001.

- [x] A cell with no wrap groups equals today's skeleton of that cell
- [x] L-shape, inner corner's two walls wrapped: one face, no valley at that
      corner, planarity holds, terrain if the rest of the cell is a normal hip
- [x] Wrapped edges share one pitch; that face reports that pitch
- [x] Wrap of non-consecutive edges is a named Failure
- [x] Wrap with disagreeing pitches is a named Failure
- [x] A wrap that cannot be a planar terrain is a named Failure
- [x] No public from-graph function; tests go through `roof` / `project`
- [x] POST of a two-edge wrap shows one face for those walls in the describe
      block
- [x] Own eave for drainage of a wrapped face is the union of the wrapped edges
