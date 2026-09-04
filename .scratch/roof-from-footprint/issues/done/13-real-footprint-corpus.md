# 13: Corpus of real footprints as regression fixtures, reported as a pass rate

**What to build:** Robustness stops being a hope and becomes a number. A corpus
of footprints from the architect's own recent projects is committed as fixtures,
every one of them asserted to produce a valid terrain, and the result reported
as a pass rate rather than a single pass or fail — so that partial progress is
visible and a regression on one building is not hidden behind a green suite.

This is the project's milestone. ADR-0001 accepted robustness as the whole risk
of owning the algorithm, and the PRD sets the milestone as "correct on real
footprints" rather than a feature count. That makes the corpus a deliverable in
its own right, not a nicety, and it is why this ticket comes after the geometry
is feature-complete.

Fixtures live in `tests/fixtures/footprints/` and the pass-rate report is
written to `docs/`. Both paths are committed to the repo — the feature's own
`.scratch/` directory is git-ignored, so neither can live beside the PRD.

The footprints themselves have to come from the architect. Where the real corpus
is not yet available, build the harness and the report against whatever is, and
say plainly in the report how many footprints it covers.

**Blocked by:** 09, 10

**Status:** done

**Prior art:** Ticket 02's invariant harness supplies every assertion this
ticket needs — the corpus is a fixture set fed through it, not a new set of
checks. Ticket 04's topology hash is what turns a fixture into a regression
test: a recorded hash per footprint catches a topology change that still
satisfies every invariant. Ticket 03's failure taxonomy decides what a fixture
that legitimately cannot be roofed should report. The feature PRD's "A corpus of
real footprints as regression fixtures" passage is the source, and its "The risk
is robustness, and it is the whole risk" note in Further Notes explains why the
pass rate is the headline number. `terrain` is a glossary term in `CONTEXT.md`.

- [x] Real footprints are committed as fixtures under
      `tests/fixtures/footprints/`, in a plain format a person can read and edit
- [x] Every fixture is run through the invariant harness from ticket 02
- [x] The result is reported as a pass rate, naming which footprints failed and
      on which property
- [x] The report is written to a committed path under `docs/`
- [x] Each passing fixture records its topology hash, so a later change that
      alters topology while keeping the invariants is caught
- [x] A fixture that cannot be roofed records its expected failure reason and is
      counted separately from a fixture that fails an invariant
- [x] Adding a footprint to the corpus requires only dropping in a file
