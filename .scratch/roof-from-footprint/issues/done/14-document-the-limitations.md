# 14: Document what this library cannot represent

**What to build:** A reader of the documentation learns, plainly and up front,
that what this library generates is a strict subset of buildable roofs — rather
than discovering it when a roof he expected does not come out.

Three things to say plainly. A straight skeleton cannot represent a roof face
spanning several footprint edges. It produces spurious vertices near certain
footprints. And roofs sharing the same footprint can have several valid styles,
of which this library generates one. Alongside those, the shapes that need
additive weights and are therefore out of reach for now — half-hips,
knee-walls, gablets, gambrels, mansards — and the roof features not modelled at
all, such as dormers and other penetrations.

The point is honesty about the boundary, not a changelog. This is documentation
for the architect deciding whether the tool covers his building, so it belongs
with the user-facing docs, at a committed path under `docs/` and linked from the
README.

**Blocked by:** 13

**Status:** done

**Prior art:** The feature PRD's Further Notes closes with "A limitation to
document rather than hide", which is this ticket's brief almost verbatim, and
its Out of Scope section lists what is excluded and why. ADR-0001 explains which
exclusions are permanent and which are merely deferred — additive weights stay
reachable, CGAL-style constraints were deliberately avoided — and that
distinction is worth passing on to the reader. `docs/future-work.md` records the
reasoning behind the parked work, so link to it rather than restating it.
`CONTEXT.md` names the roof types in and out of the model. Ticket 13's pass-rate
report is the empirical companion to this prose: what fails, next to what cannot
be represented at all.

- [x] A limitations document exists at a committed path under `docs/`, linked
      from the README
- [x] It states the three straight-skeleton limitations above in terms an
      architect reads, not in terms of the algorithm
- [x] It lists the roof types out of scope and distinguishes deferred from
      permanent, pointing at `docs/future-work.md` for the reasoning
- [x] It does not imply completeness anywhere
