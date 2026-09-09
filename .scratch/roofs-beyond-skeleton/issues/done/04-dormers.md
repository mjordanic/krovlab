# 04: Dormers

**Prerequisite:** Same as ticket 01 — project-from-cells already on the branch.

**What to build:** The architect places a dormer by drawing a small footprint on
a host face, with its own pitch (gable or shed). Several dormers on one project
are several placements. A dormer that does not sit on a single host face, or
that lies outside the host, is refused by name.

`project` roofs every cell first (including knee, gambrel, wrap), then locates
each dormer by plan overlap onto exactly one face of that cell. The child is the
one-footprint function on the dormer ring, lifted onto the host plane — the
dormer's eave is the intersection with the host, not the building eave. Clip.
Host sloped area loses the opening; dormer faces add. Prefer not inventing a new
arc kind until a test needs it.

A project with dormers is not a single terrain. Validity says so. Quantities
remain usable. 3D still draws (host with a hole, dormer on top). This is the
documented exception to "no 3D unless terrain". A plus-shape or other broken
skeleton still hides 3D.

A dormer on a wrapped face still clips that one plane. Millimetre tables for
dormer rings remain. Submit is still POST.

**Blocked by:** 03 wrap consecutive edges

**Status:** done

**Complexity:** high

**Stories:** 11, 12, 13, 14, 15, 16, 17, 18, 19, 27, 30, 31

**Prior art:** Feature PRD "Dormers after the host exists", "A project with
dormers is not a single terrain", and the 2 × 1.5 m gable-dormer worked example.
Form-server three result branches — this ticket is the one exception for 3D.
Plus-shape POST still plan-only (project-from-cells and form-server). Ticket 03
for wrap so a dormer on a wrapped face is testable. Do not add a public
from-graph or a third engine.

- [x] Rectangle plus one gable dormer whose plan is a 2 × 1.5 m rectangle on a
      long slope: host sloped area decreases by the opening; dormer adds two or
      three faces
- [x] Plan areas of host-plus-dormer still cover the host footprint; the opening
      is not double-counted
- [x] The project is not a terrain; the describe block says so; 3D still builds
- [x] A shed dormer and a gable dormer use the same placement tool (pitch list
      on the dormer ring)
- [x] Several dormers on one project are several placements
- [x] Dormer overlapping two faces is a named Failure
- [x] Dormer outside the host is a named Failure
- [x] A dormer on a wrapped face clips that one plane
- [x] POST of a drawn dormer rectangle matches `project` with that dormer
- [x] A plus-shape POST still shows plan, validity reasons, and no 3D
- [x] Tests go through `project`; Failure is a value; core imports no Flask
