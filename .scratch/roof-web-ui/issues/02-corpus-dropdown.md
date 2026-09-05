# 02: Corpus dropdown

**What to build:** The power user picks a named footprint from the project's
corpus and submits. The page runs that fixture's rings, pitch, and overhang
through `roof` and shows the matching result branch.

The list includes at least the rectangle, L, U, courtyard, gabled rectangle, and
bowtie. Choosing a name fills whatever form fields already exist (and must fill
the coordinate and pitch tables once ticket 04 adds them). The dropdown is the
corpus, not a second hand-copied geometry list.

The bowtie is the Failure demo: `kind` is `self_intersection`, `reason` is shown,
the input footprint is drawn, and there is no plan of a roof and no 3D. The
courtyard and the gabled rectangle are terrain Roofs with 3D; the gabled plan
includes a verge.

**Blocked by:** 01

**Status:** ready-for-agent

**Stories:** 4, 5 (preset loads the fixture into the form; tables in 04), 6, 7, 8, 21, 22, 28

**Prior art:** Corpus fixtures and loader (`rectangle-10x6`, `l-shape`,
`u-shape`, `courtyard`, `rectangle-gabled`, `bowtie`, …). Failure as a value:
`Failure.kind` / `Failure.reason`, `self_intersection` tests on the roof entry
point. Notebook `show` / `footprint_outline` on Failure — the web app owns that
drawing; do not add it to viz. PRD result-branch table and the bowtie / gabled /
courtyard HTTP cases.

- [ ] Dropdown lists the corpus footprints by name, not a parallel coordinate list
- [ ] Submitting the bowtie returns Failure `self_intersection`, draws the input footprint, and omits 3D
- [ ] Submitting the courtyard returns a terrain Roof with plan and 3D
- [ ] Submitting the gabled rectangle returns a terrain Roof whose plan includes a verge, with 3D
- [ ] Picking a fixture loads that fixture's rings, pitch, and overhang into the form
- [ ] Flask test client covers bowtie, courtyard, and gabled rectangle POSTs
