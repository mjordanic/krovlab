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

**Status:** done

**Stories:** 4, 5, 6, 10, 11, 12, 21, 22, 23 (finishes: shared edges agree), 36,
37, 41

**Prior art:** Feature PRD "Shared walls are geometry, not a join argument" and
the hand-computed 5 m / 7 m example in Testing Decisions. Adjacent parallel
pitches on one cell remain unsupported (existing input check). Corpus presets
load rings, pitch, and overhang into the form (form-server ticket 01). Vertex
tolerance already used for coincident points on a single footprint.

- [x] Two 5 × 6 m gable cells sharing a party wall at eave heights 5 m and 7 m,
      pitch 45°, yield project ridge height 9.5 m, plan area 60 m², both
      terrains, no overlap
- [x] That party wall is not counted twice as eaves in the takeoff
- [x] Two cells that share a pitched edge at the same eave height meet as one
      valley, counted once
- [x] Shared edge gable versus pitch is a named Failure
- [x] Shared pitched edge with unequal eave heights is a named Failure
- [x] Two pitches on collinear edges of one cell remain Failure `unsupported`
- [x] Corpus dropdown includes the concatenated-gables fixture
- [x] Picking that fixture fills both cells; POST reports ridge height 9.5 m,
      terrain, plan, and 3D

## Comments

`project` detects coincident outer edges to the existing vertex
tolerance. Both gables: party wall, roofs unstitched, eaves not doubled.
Both pitched at the same eave height: the two eaves become one valley.
`gable_versus_pitch` and `unequal_eave_height` refuse the other pairings.
Collinear two-pitch on one cell still goes through `roof` as `unsupported`.

The PRD's 2.5 m / 9.5 m ridge is the hip span (half of 5 m). A gable on
the 6 m party wall has span 6 m, so each ridge is 3 m above its eave and
the project ridge is 10 m. The corpus fixture and page report 10 m.

`concatenated-gables.toml` is a `[[cells]]` fixture in the footprints
directory. The roof corpus skips it; the page dropdown loads it and
fills both cells.
