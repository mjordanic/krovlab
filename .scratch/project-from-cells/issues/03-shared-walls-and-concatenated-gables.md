# 03: Shared walls and concatenated gables

**What to build:** Shared walls are coincident edges, not a join the architect
names. Two edges coincide when they lie on the same segment to the existing
vertex tolerance.

If both are gables, they are a party wall: the roofs do not stitch, and the
takeoff does not count two eaves for that wall. If both are pitched and eave
height matches, the two eaves are one valley — the inner gutter is one run. Any
other pairing is a named Failure (gable versus pitch; pitched with unequal eave
heights). Two pitches on collinear segments of one cell stay unsupported.

The worked case is two 5 × 6 m gable cells sharing the party wall at x = 5,
plate heights 5 m and 7 m, pitch 45°. Each cell's ridge is 2.5 m above its eave;
absolute ridges are 7.5 m and 9.5 m. Project ridge height is 9.5 m. Plan areas
sum to 60 m². Both cells are terrains. No overlap.

A committed corpus fixture of that pair is a dropdown pick. Choosing it fills
both cells' rings, pitches, and eave heights. Submitting it reports those
numbers, terrain, plan, and 3D.

**Blocked by:** 02 project of cells

**Status:** ready-for-agent

**Stories:** 4, 5, 6, 10, 11, 12, 21, 22, 23 (finishes: shared edges agree), 36,
37, 41

**Prior art:** Feature PRD "Shared walls are geometry, not a join argument" and
the hand-computed 5 m / 7 m example in Testing Decisions. Adjacent parallel
pitches on one cell remain unsupported (existing input check). Corpus presets
load rings, pitch, and overhang into the form (form-server ticket 01). Vertex
tolerance already used for coincident points on a single footprint.

- [ ] Two 5 × 6 m gable cells sharing a party wall at eave heights 5 m and 7 m,
      pitch 45°, yield project ridge height 9.5 m, plan area 60 m², both
      terrains, no overlap
- [ ] That party wall is not counted twice as eaves in the takeoff
- [ ] Two cells that share a pitched edge at the same eave height meet as one
      valley, counted once
- [ ] Shared edge gable versus pitch is a named Failure
- [ ] Shared pitched edge with unequal eave heights is a named Failure
- [ ] Two pitches on collinear edges of one cell remain Failure `unsupported`
- [ ] Corpus dropdown includes the concatenated-gables fixture
- [ ] Picking that fixture fills both cells; POST reports ridge height 9.5 m,
      terrain, plan, and 3D
