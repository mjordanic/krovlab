# krovlab

Give a building footprint in metres and a pitch in degrees. Get back
the faces, hips, ridges, valleys and quantities of a hipped roof — or a
named failure. Give several footprints as cells and get one project. An
edge can carry a knee height or a gambrel; a dormer is a small ring on
a host face.

The roofs it generates are a strict subset of roofs you can build. Read
[what it cannot represent](docs/limitations.md) before deciding whether
it covers a given building. Always read `validity.is_terrain` before
trusting the numbers: some plans come back as a `Roof` that is not a
valid terrain.

The core has no third-party dependencies. It takes data and returns data.

## Install

Python 3.13+. From the repo root:

```bash
uv sync
```

Optional extras:

```bash
uv sync --extra viz         # Plotly, for plan / 3D / wavefront views
uv sync --extra notebooks   # ipykernel + Plotly, to run the notebooks
uv sync --extra web         # Flask form server wrapping roof
```

## Quick start

```python
from krovlab import Cell, Dormer, Failure, Roof, project, roof, topology_hash

footprint = [(0, 0), (10, 0), (10, 6), (0, 6)]  # metres, either winding
result = roof(footprint, 45)                    # degrees

if isinstance(result, Failure):
    print(result.kind, result.reason)   # branch on kind; show reason
else:
    print(result.validity.is_terrain)   # check this before using quantities
    print(result.ridge_height)          # 3.0 m
    print(result.total_sloped_area)     # covering area, m²
    print(topology_hash(result))        # combinatorial structure, not coordinates
```

`roof` roofs one footprint. `project` roofs a list of cells, optionally
with dormers. Knee and gambrel live on the same two functions and on
`Cell`. Everything else — the wavefront, the event queue, the
conversion of pitch to weight — stays behind those two functions.

## Examples

### Pitch spellings

Pitch is the angle from horizontal. These four calls are the same 45° roof:

```python
roof(footprint, 45)          # degrees
roof(footprint, (1, 1))      # rise:run  →  atan(1/1) = 45°
roof(footprint, "1:1")       # same ratio as a string ("4:12" is US 4/12)
roof(footprint, "100%")      # percent    →  atan(1.00) = 45°
```

A list is one value per footprint edge (outer ring first, then each hole).
The length must match. Differing pitches weight the wavefront so each face
rises at its own pitch. Adjacent parallel edges of differing pitch are
refused: that configuration has no unique straight skeleton.

After conversion the angle must satisfy `0 < pitch <= 90`. Outside that
range, or a list of the wrong length, you get a `Failure`, not an exception.

`pitch = 90` is a gable end: that edge does not move, produces no face,
and the neighbouring faces meet the wall at verges. Gabling every edge is
`incomplete`.

Weight (`cot(pitch)`) is an internal wavefront speed. It never appears on
the returned roof.

### A rectangle, an L, a courtyard, a gable, an overhang, an eave height, two cells, a knee, a gambrel, a dormer

```python
import math

from krovlab import Cell, Dormer, project, roof

rect = [(0, 0), (10, 0), (10, 6), (0, 6)]
l_shape = [(0, 0), (10, 0), (10, 6), (3, 6), (3, 10), (0, 10)]
square = [(0, 0), (10, 0), (10, 10), (0, 10)]
courtyard = [(3, 3), (7, 3), (7, 7), (3, 7)]

hipped = roof(rect, 45)
# One 4 m ridge at height 3 m.

valleys = roof(l_shape, 45)
# One valley from the reflex corner.

around = roof(square, 45, holes=[courtyard])
# Inward eaves on the courtyard; valleys from its corners;
# a ridge square where the two wavefronts meet. Ridge height 1.5 m.
# A single pitch covers the hole edges too — you do not need a list.

# Approximate a circle with an n-gon. Each segment is still one wall.
n, r = 16, 1.5
round_well = [
    (5 + r * math.cos(2 * math.pi * i / n), 5 + r * math.sin(2 * math.pi * i / n))
    for i in range(n)
]
round_roof = roof(square, 45, holes=[round_well])

# Vertical inner walls (a light well at eave height): gable every hole edge.
# This is not a chimney. A chimney is a hole *through the slope*, which
# the model does not carry.
well = roof(square, [45, 45, 45, 45, 90, 90, 90, 90], holes=[courtyard])

# Pitch lists cover outer edges, then hole edges, in order.
mixed = roof(square, [60, 45, 60, 45])
# Steeper east/west faces; a ridge along x = 5.

gabled = roof(rect, [45, 90, 45, 45])
# East wall is a gable: no face there, two verges, ridge meets the wall.

shed = roof(rect, [45, 90, 90, 90])
# Three gables leave a single sloping face.

eaves = roof(rect, 45, overhang=0.5)
# Eaves sit 0.5 m past the walls. The roof is of the enlarged footprint.
# A hole shrinks by the same amount. Zero overhang is the same as omitting it.
# An overhang that closes a courtyard or folds a thin wing is a named Failure.
# In the drawings, pass the original walls so they stay distinct from the eaves:
#   plan_view(eaves, walls=rect)     # brown = walls, grey eave = roof edge
#   solid_view(eaves, walls=rect)

lifted = roof(rect, 45, eave_height=7)
# Same roof on a 7 m plate. Ridge height 10 m. Plan areas unchanged.
# Terrain is assessed at the eave plane, then every node is lifted.

house = [(0, 0), (5, 0), (5, 6), (0, 6)]
garage = [(8, 0), (13, 0), (13, 6), (8, 6)]
lot = project(
    [
        Cell(house, 45, eave_height=5),
        Cell(garage, 45, eave_height=7),
    ]
)
# Two detached 5 × 6 m hips. Plan areas sum to 60 m². Project ridge
# height is 9.5 m. Each face names its cell and that cell's edge.
# Overlapping cells are a named Failure. An L drawn as one polygon is
# still one cell — the library does not cut it.

neighbour = [(5, 0), (10, 0), (10, 6), (5, 6)]
gables = [45, 90, 45, 90]
pair = project(
    [
        Cell(house, gables, eave_height=5),
        Cell(neighbour, gables, eave_height=7),
    ]
)
# Two concatenated gables sharing the party wall at x = 5. Each
# ridge is 3 m above its eave, so the project ridge is 10 m. The
# party wall is not counted twice as eaves. Two pitched eaves on that
# wall at the same eave height meet as one valley. A gable against a
# pitch, or pitched eaves at two heights, is a named Failure.

gablet = roof(rect, 45, knee_height=[0, 3, 0, 0])
# East short wall rises 3 m — the would-be full-hip ridge — then a
# vertical gablet. Neighbours close as verges. Ridge height still 3 m.
# Zero knee height is the same roof as omitting it. Gable plus knee on
# the same edge is gable_versus_knee.

barn = roof(
    rect,
    45,
    gambrel=[(60, 30, 3**0.5), None, (60, 30, 3**0.5), None],
)
# Long walls 60° then 30°, break √3 m above the eave. Two faces per
# long wall; plan areas still sum to 60 m². Gambrel plus knee, or
# gambrel plus gable, on the same edge is a named Failure.

dormered = project(
    [Cell(rect, 45)],
    [Dormer(0, [(4, 0.5), (6, 0.5), (6, 2), (4, 2)], [45, 90, 45, 90])],
)
# 2 × 1.5 m gable dormer on the south slope. Host sloped area loses
# the opening; dormer faces add. Not a terrain; 3D still draws. A
# dormer over two faces, or outside the host, is a named Failure.
```

Either winding is accepted. A closed-ring spelling (first point repeated
at the end) is accepted. Collinear extra vertices on a straight wall are
kept when they share a pitch — two faces of one plane, not one face
spanning both. Differing pitches on those halves are `unsupported`.

### Reading a `Roof`

| Attribute | What it is |
|---|---|
| `nodes` | Every vertex. Height is metres above datum. Footprint corners sit at the eave height (zero by default). |
| `faces` | One face per non-gabled footprint edge, except a gambrel edge is two. `edge_index` is the edge you passed in. Faces from `roof` have no cell index. |
| `arcs` | `kind` is `"eave"`, `"hip"`, `"valley"`, `"ridge"` or `"verge"`; `length` is 3D metres. |
| `ridge_height` | Highest point above datum. |
| `total_sloped_area` | Sum of `face.sloped_area` — what covering is bought by. |
| `validity` | Whether the roof is a terrain. Check `is_terrain` before using anything else. |

Each face splits area in two: `plan_area` (horizontal projection) and
`sloped_area` (`plan_area / cos(pitch)`). Plan areas sum to the footprint
area with holes excluded — or to the enlarged footprint when an overhang
is applied.

`Face.edge_index` `i` is the edge from `footprint[i]` to
`footprint[(i + 1) % n]` on the outer ring, then continues through each
hole in order, even if you passed a ring clockwise. A `Project` face
adds `cell_index`: which cell that edge belongs to.

A `Roof` is checked when it is built. If `validity.is_terrain` is false,
`validity.reasons` names the invariant that broke. Simple convex, L and U
footprints at uniform pitch typically pass. Crossing-arm plans, some
T-shapes, mixed pitch on some L-shapes, and a gable on some reflex edges
can come back as a `Roof` that is not a terrain — not as an exception,
and not always as a `Failure`. A project with dormers is also not a
terrain; covering numbers still add up and 3D still draws.

`topology_hash(roof)` is a stable hash of which faces meet which arcs at
which nodes, not of their coordinates.

To inspect the wavefront events that produced a roof, pass `events=True`.
The return is `(Roof, events)`. Each event has a `kind`, a `time` (height
in metres), the footprint `edges` it involved, and the node `vertices` it
involved.

### Plan, 3D and wavefront views

`krovlab.viz` is an optional extra. It consumes a `Roof` and returns a
Plotly figure. Save any view as a self-contained HTML file that opens
from disk:

```python
from krovlab.viz import plan_view, solid_view, wavefront_steps, wavefront_view, write_html

fig = plan_view(result)
write_html(fig, "roof-plan.html")
write_html(solid_view(result), "roof-solid.html")

# Overhang: pass the original walls so the brown line is the building
# and the eave line is where the roof ends, 0.5 m beyond.
overhung = roof(footprint, 45, overhang=0.5)
write_html(plan_view(overhung, walls=footprint), "overhang-plan.html")
write_html(solid_view(overhung, walls=footprint), "overhang-solid.html")

write_html(wavefront_view(result, 1.5), "roof-wavefront.html")

logged = roof(footprint, 45, events=True)
if not isinstance(logged, Failure):
    built, events = logged
    for i, step in enumerate(wavefront_steps(built, events)):
        write_html(step, f"wavefront-{i:02d}.html")
```

The plan is the skeleton over the roof's plan extent, arcs coloured by
type, node heights annotated. Pass `walls=` to draw the building
outline separately — needed when an overhang puts the eaves outside the
walls. The 3D view is orbitable. The wavefront view is the shrinking
polygon at a chosen time (time is height).

The core never imports this module. Without the extra, `import krovlab`
still works.

### When `roof` or `project` cannot start

Bad input is a `Failure` with a `kind` you can branch on and a `reason`
you can show. Nothing the entry point accepts raises.

| `kind` | What it means |
|---|---|
| `invalid_pitch` | Unreadable spelling, or outside `0 < pitch <= 90`. |
| `pitch_count` | Pitch list length is not the number of footprint edges. |
| `self_intersection` | The footprint crosses itself. |
| `degenerate` | A point, a line, coincident consecutive vertices, or no area. |
| `hole_intersects` | A hole touches or crosses the outer ring, or another hole. |
| `unsupported` | Adjacent parallel edges of differing pitch (no unique skeleton). |
| `incomplete` | The wavefront stopped before the skeleton finished, including when every edge is a gable. |
| `empty` | `project` was given no cells. |
| `overlap` | Two cells overlap in plan. |
| `gable_versus_pitch` | A shared edge is a gable on one cell and pitched on the other. |
| `unequal_eave_height` | A pitched shared edge sits at two eave heights. |
| `gable_versus_knee` | The same edge is a gable and has a knee height. |
| `gambrel_versus_knee` | The same edge is a gambrel and has a knee height. |
| `gambrel_versus_gable` | The same edge is a gambrel and a gable. |
| `dormer_two_faces` | A dormer overlaps two host faces. |
| `dormer_outside` | A dormer does not lie on a host face. |

A `Failure` means no roof was produced. A `Roof` with
`validity.is_terrain == False` means a roof was produced and then failed
the checks — treat it as unusable, except a project whose only reason is
dormers: the host has a hole, covering numbers still add up, and 3D
still draws. Units on a valid roof are metres and degrees.

## Web demo

A form page that wraps `roof` / `project` and the existing plan and 3D views. From the
repo root:

```bash
uv sync --extra web
uv run --extra web python -m web
```

Open http://127.0.0.1:5000 — the 10 × 6 m rectangle at 45° is already run.
Pick a named footprint from the project's corpus and submit to see the
matching roof, or a Failure with the input drawn. `concatenated-gables`
is two cells at plate heights 5 m and 7 m. Click vertices on the plan to
draw a cell, close the ring, and add another. Click an edge to set knee
height or a gambrel; draw a rectangle on a host face for a dormer.
Millimetre tables stay in sync. Submit is still one form POST.

The same process is what a container runs. `Dockerfile` at the repo root
starts it on Python 3.13, binds `0.0.0.0`, and honours `PORT` (8080 in the
image). Plotly.js still comes from a CDN.

```bash
docker build -t krovlab .
docker run --rm -p 8080:8080 krovlab
```

To give it a URL, deploy that image to Cloud Run: region `europe-west1`,
min instances 0, unauthenticated. No custom domain. Do not run this from
CI — there is no live Google Cloud project in the test suite.

```bash
gcloud run deploy krovlab \
  --source . \
  --region europe-west1 \
  --min-instances 0 \
  --allow-unauthenticated
```

## Worked numbers

A 10 m square at 45° has apex height 5 m and four faces of 25 m² plan /
`25 / cos(45°)` sloped. A 10 × 6 m rectangle at 45° has a 4 m ridge at
height 3 m, from `(3, 3, 3)` to `(7, 3, 3)`. The same roof at eave height
7 m has ridge height 10 m. Two detached 5 × 6 m hips at eave heights 5 m
and 7 m have project ridge height 9.5 m and plan area 60 m². Two 5 × 6 m
gables sharing a party wall at those plate heights have project ridge
height 10 m: each ridge is 3 m above its eave. A 10 m square with pitches
`[60, 45, 60, 45]` has a 5 m ridge along `x = 5` of length `10 - 10/√3`.
A 10 m square with a centred 4 m courtyard at 45° has ridge height 1.5 m
and plan area 84 m²: four hips from the outer corners, four valleys from
the courtyard corners, and a 7 m ridge square where the wavefronts meet.
A 10 × 6 m rectangle at 45° with a 3 m knee on the east short edge is a
vertical gablet: ridge height still 3 m, ridge length 7 m, two verges.
The same rectangle with long edges gambrel 60° then 30° at break √3 m
has two faces per long wall; plan areas still sum to 60 m². A 2 × 1.5 m
gable dormer on the south slope of the rectangle is not a terrain; host
sloped area loses the opening.

## Notebooks

Step-through examples after `uv sync --extra notebooks`:

- [`notebooks/getting-started.ipynb`](notebooks/getting-started.ipynb) —
  call `roof`, read quantities, gables, holes, overhang, eave height,
  a project of two cells, concatenated gables and a valley, knee
  (gablet), gambrel, a dormer on a host face, drawing those on
  the form page, and the views.
- [`notebooks/limitations.ipynb`](notebooks/limitations.ipynb) — plans
  that fail the terrain check, the dormer exception (not a terrain, 3D
  still draws), inherent method limits, and how to read `validity`.

## Tests

```bash
uv run pytest
uv run mypy src tests
uv run ruff check src tests
```

`tests/test_invariants.py` generates simple footprints (convex, L, U)
and rectangles with holes, and asserts the terrain invariants (areas,
planarity, drainage, arc labels, determinism). Convex cases also draw a
different pitch per edge. Generated cases include a modest eaves
overhang.

A corpus of footprints lives in `tests/fixtures/footprints/` (plain TOML;
drop in a file to add one). Each is run through the same invariant
harness and reported as a pass rate in
[`docs/footprint-corpus.md`](docs/footprint-corpus.md). The files there
today are stand-ins from the worked examples, not yet the architect's
own buildings.

## Glossary

Terms (`footprint`, `face`, `pitch`, `plan area`, `sloped area`, `ridge`,
`hip`, `valley`, `eave`) are defined in [`CONTEXT.md`](CONTEXT.md). The
algorithm choice is recorded in
[`docs/adr/0001-own-weighted-straight-skeleton-in-python.md`](docs/adr/0001-own-weighted-straight-skeleton-in-python.md).
What the library cannot represent — including which plans currently
fail the terrain check — is in [`docs/limitations.md`](docs/limitations.md).
