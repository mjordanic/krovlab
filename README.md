# krovlab

Roof geometry from a building footprint. You give a polygon in metres and a
pitch in degrees; you get back the faces, hips, ridges and quantities of a
hipped roof.

The core has no third-party dependencies. It takes data and returns data.

## What it does today

Simple footprints (convex, L, U) and footprints with holes. A square at
one pitch becomes a pyramid of four triangular faces; a rectangle gets a
ridge; an L-shape produces one valley; a courtyard produces inward eaves
and valleys where the two wavefronts meet. A different pitch per edge is
accepted. `pitch = 90` on an edge is a gable: no face over that edge,
neighbouring faces meeting the wall at verges. Gabling every edge is
`incomplete`. Mixed pitch on an L or U can still come back `incomplete`.
`overhang` (metres) offsets the footprint outward before the roof is
generated — eaves sit past the walls, and a hole shrinks. An overhang
that closes a hole or folds a thin wing is a named `Failure`.
`krovlab.viz` draws a plan, an orbitable 3D solid, and the wavefront at a
chosen time.

## Install

Python 3.13+. From the repo root:

```bash
uv sync
```

That puts `krovlab` on the path of the project environment. Optional extras:

```bash
uv sync --extra viz         # Plotly, for krovlab.viz plan, 3D and wavefront views
uv sync --extra notebooks   # ipykernel + Plotly + nbformat, to run the notebooks
```

## Quick start

```python
from krovlab import Failure, Roof, roof, topology_hash

footprint = [(0, 0), (10, 0), (10, 6), (0, 6)]  # metres, either winding
result = roof(footprint, 45)                    # degrees

# A courtyard is a second ring. Pitch lists cover outer edges then hole edges.
courtyard = roof(footprint, 45, holes=[[(2, 2), (8, 2), (8, 4), (2, 4)]])

# Eaves overhang is metres past the walls. The roof is of the enlarged footprint.
eaves = roof(footprint, 45, overhang=0.5)

if isinstance(result, Failure):
    print(result.kind, result.reason)   # branch on kind; show reason
else:
    print(result.ridge_height)       # 3.0 m
    print(result.total_sloped_area)  # covering area, m²
    print(result.validity.is_terrain)
    print(topology_hash(result))     # combinatorial structure, not coordinates
```

`roof` is the only entry point. Everything else — the wavefront, the event
queue, the conversion of pitch to weight — stays behind it.

### Pitch

Pitch is the angle from horizontal. Write it in whichever convention the
drawing uses — the three spellings of the same slope produce the same roof:

```python
roof(footprint, 45)          # degrees
roof(footprint, (1, 1))      # rise:run  →  atan(1/1) = 45°
roof(footprint, "1:1")       # same ratio as a string
roof(footprint, "100%")      # percent    →  atan(1.00) = 45°
```

A list is one value per footprint edge. The length must match — outer
ring first, then each hole in order. Differing pitches weight the
wavefront so each face rises at its own pitch. Adjacent parallel edges
of differing pitch are refused: that configuration has no unique
straight skeleton. `pitch = 90` is a gable end: that edge does not
move, produces no face, and the neighbouring faces meet the wall at
verges.

`overhang` is metres of eaves projection. The library offsets the
footprint outward (and each hole inward) and roofs the enlarged polygon.
Zero overhang is the same roof as omitting the argument. An overhang
large enough to close a courtyard or fold a concave footprint comes back
as a `Failure` (`degenerate` or `self_intersection`), not an exception.

After conversion the angle must satisfy `0 < pitch <= 90`. Outside that
range, or a list of the wrong length, you get a `Failure`, not an exception.

Weight (`cot(pitch)`) is an internal wavefront speed. It never appears on the
returned roof.

### Reading a `Roof`

| Attribute | What it is |
|---|---|
| `nodes` | Every vertex. Footprint corners have `height == 0`. |
| `faces` | One face per non-gabled footprint edge. `edge_index` is the edge you passed in. |
| `arcs` | `kind` is `"eave"`, `"hip"`, `"valley"`, `"ridge"` or `"verge"`; `length` is 3D metres. |
| `ridge_height` | Highest point above the eave plane. |
| `total_sloped_area` | Sum of `face.sloped_area` — what covering is bought by. |
| `validity` | Whether the roof is a terrain. `is_terrain` is true only when plan areas sum to the footprint, every face is planar, sampled plan points have one height, water drains to each face's own eave, and arc labels match the geometry. |

Each face also splits area in two: `plan_area` (horizontal projection) and
`sloped_area` (`plan_area / cos(pitch)`). Plan areas sum to the footprint
area with holes excluded — or to the enlarged footprint when an overhang
is applied.

`Face.edge_index` `i` is the edge from `footprint[i]` to
`footprint[(i + 1) % n]` on the outer ring, then continues through each
hole in order, even if you passed a ring clockwise.

A `Roof` is checked when it is built. If `validity.is_terrain` is false,
`validity.reasons` names the invariant that broke — so you find out from the
value, not on site.

`topology_hash(roof)` is a stable hash of which faces meet which arcs at
which nodes, not of their coordinates. Two roofs that differ only in a
vertex position hash the same; two that differ in which faces meet do not.

To inspect the wavefront events that produced a roof, pass `events=True`.
The return is `(Roof, events)` — the roof is unchanged, and callers that
omit the flag are not handed debugging state. Each event has a `kind`, a
`time` (height in metres), the footprint `edges` it involved, and the
node `vertices` it involved.

### Plan, 3D and wavefront views

`krovlab.viz` is an optional extra. It consumes a `Roof` and returns a
Plotly figure. The plan view is the footprint with the skeleton over it,
arcs coloured by type (ridge, hip, valley, eave, verge), node heights
annotated. The 3D view is the roof solid, orbitable, built from the
faces and the node heights the roof already carries. The wavefront view
is the shrinking polygon at a chosen time — time is height, so
`wavefront_view(roof, 1.5)` is the cut at 1.5 m. Pass the event log from
`events=True` to `wavefront_steps` to page through the exact instants
the topology changed. Negative time and time past the ridge still
produce a figure (empty wavefront over the footprint). Save any view as
a self-contained HTML file that opens from disk:

```python
from krovlab.viz import plan_view, solid_view, wavefront_steps, wavefront_view, write_html

fig = plan_view(result)
write_html(fig, "roof-plan.html")

write_html(solid_view(result), "roof-solid.html")
write_html(wavefront_view(result, 1.5), "roof-wavefront.html")

logged = roof(footprint, 45, events=True)
if not isinstance(logged, Failure):
    built, events = logged
    for i, step in enumerate(wavefront_steps(built, events)):
        write_html(step, f"wavefront-{i:02d}.html")
```

The core never imports this module. Without the extra, `import krovlab`
still works.

### When `roof` cannot run

Bad input is a `Failure` with a `kind` you can branch on and a `reason` you
can show. Nothing the entry point accepts raises.

| `kind` | What it means |
|---|---|
| `invalid_pitch` | Unreadable spelling, or outside `0 < pitch <= 90`. |
| `pitch_count` | Pitch list length is not the number of footprint edges. |
| `self_intersection` | The footprint crosses itself. |
| `degenerate` | A point, a line, coincident consecutive vertices, or no area. |
| `hole_intersects` | A hole touches or crosses the outer ring, or another hole. |
| `unsupported` | Adjacent parallel edges of differing pitch (no unique skeleton). |
| `incomplete` | The wavefront stopped before the skeleton finished, including when every edge is a gable. |

A closed-ring spelling (first point repeated at the end) is accepted. Either
winding produces the same roof. Collinear vertices that still enclose area
are roofed; they are the same building with an extra point on an eave.
Units on the returned roof are metres and degrees.

## Worked numbers

A 10 m square at 45° has apex height 5 m and four faces of 25 m² plan /
`25 / cos(45°)` sloped. A 10 x 6 m rectangle at 45° has a 4 m ridge at
height 3 m, from `(3, 3, 3)` to `(7, 3, 3)`. A 10 m square with pitches
`[60, 45, 60, 45]` has a 5 m ridge along `x = 5` of length `10 - 10/√3`.
A 10 m square with a centred 4 m courtyard at 45° has ridge height 1.5 m
and plan area 84 m²: four hips from the outer corners, four valleys from
the courtyard corners, and a 7 m ridge square where the wavefronts meet.

## Notebooks

Examples you can step through:

- [`notebooks/getting-started.ipynb`](notebooks/getting-started.ipynb) — call
  `roof`, read quantities, draw a plan of the skeleton.

Open [`notebooks/getting-started.ipynb`](notebooks/getting-started.ipynb) in the
editor after `uv sync`. The project kernel provides `krovlab`; the last cells
draw a plan with Plotly.

## Tests

```bash
uv run pytest
uv run mypy src tests
uv run ruff check src tests
```

`tests/test_invariants.py` generates simple footprints (convex, L, U) and
rectangles with holes, and asserts the terrain invariants (areas, planarity,
drainage, arc labels, determinism). Convex cases also draw a different
pitch per edge. Generated cases include a modest eaves overhang. Later
geometry tickets widen `tests/generation.py` rather than copying those
assertions.

A corpus of footprints lives in `tests/fixtures/footprints/` (plain TOML;
drop in a file to add one). Each is run through the same invariant
harness and reported as a pass rate in
[`docs/footprint-corpus.md`](docs/footprint-corpus.md). Passing fixtures
record a topology hash so a later change that keeps the invariants but
alters structure is caught. The files there today are stand-ins from the
worked examples, not yet the architect's own buildings.

## Glossary

Terms (`footprint`, `face`, `pitch`, `plan area`, `sloped area`, `ridge`,
`hip`, `valley`, `eave`) are defined in [`CONTEXT.md`](CONTEXT.md). The algorithm
choice is recorded in [`docs/adr/0001-own-weighted-straight-skeleton-in-python.md`](docs/adr/0001-own-weighted-straight-skeleton-in-python.md).
