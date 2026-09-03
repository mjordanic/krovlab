# krovlab

Roof geometry from a building footprint. You give a polygon in metres and a
pitch in degrees; you get back the faces, hips, ridges and quantities of a
hipped roof.

The core has no third-party dependencies. It takes data and returns data.

## What it does today

Convex footprints, one pitch for the whole roof. A square becomes a pyramid of
four triangular faces. A rectangle becomes two trapezoids, two triangles and a
ridge. L-shapes, holes, gables, overhang and per-edge pitch are not built yet.

## Install

Python 3.13+. From the repo root:

```bash
uv sync
```

That puts `krovlab` on the path of the project environment. Optional extras:

```bash
uv sync --extra viz         # Plotly, for the notebook plan view
uv sync --extra notebooks   # ipykernel + Plotly + nbformat, to run the notebooks
```

## Quick start

```python
from krovlab import Failure, Roof, roof

footprint = [(0, 0), (10, 0), (10, 6), (0, 6)]  # metres, either winding
result = roof(footprint, 45)                    # degrees

if isinstance(result, Failure):
    print(result.kind, result.reason)   # branch on kind; show reason
else:
    print(result.ridge_height)       # 3.0 m
    print(result.total_sloped_area)  # covering area, m²
    print(result.validity.is_terrain)
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

A list is one value per footprint edge. The length must match. Today every
value must convert to the same slope; differing per-edge pitches come later.

After conversion the angle must satisfy `0 < pitch <= 90`. Outside that
range, or a list of the wrong length, you get a `Failure`, not an exception.

Weight (`cot(pitch)`) is an internal wavefront speed. It never appears on the
returned roof.

### Reading a `Roof`

| Attribute | What it is |
|---|---|
| `nodes` | Every vertex. Footprint corners have `height == 0`. |
| `faces` | One face per footprint edge. `edge_index` is the edge you passed in. |
| `arcs` | `kind` is `"eave"`, `"hip"` or `"ridge"`; `length` is 3D metres. |
| `ridge_height` | Highest point above the eave plane. |
| `total_sloped_area` | Sum of `face.sloped_area` — what covering is bought by. |
| `validity` | Whether the roof is a terrain. `is_terrain` is true only when plan areas sum to the footprint, every face is planar, sampled plan points have one height, water drains to each face's own eave, and arc labels match the geometry. |

Each face also splits area in two: `plan_area` (horizontal projection) and
`sloped_area` (`plan_area / cos(pitch)`). Plan areas sum to the footprint area.

`Face.edge_index` `i` is the edge from `footprint[i]` to
`footprint[(i + 1) % n]`, even if you passed the ring clockwise.

A `Roof` is checked when it is built. If `validity.is_terrain` is false,
`validity.reasons` names the invariant that broke — so you find out from the
value, not on site.

### When `roof` cannot run

Bad input is a `Failure` with a `kind` you can branch on and a `reason` you
can show. Nothing the entry point accepts raises.

| `kind` | What it means |
|---|---|
| `invalid_pitch` | Unreadable spelling, or outside `0 < pitch <= 90`. |
| `pitch_count` | Pitch list length is not the number of footprint edges. |
| `self_intersection` | The footprint crosses itself. |
| `degenerate` | A point, a line, coincident consecutive vertices, or no area. |
| `hole_intersects` | A hole touches or crosses the outer ring. |
| `unsupported` | A valid hole, or differing per-edge pitches — not built yet. |

A closed-ring spelling (first point repeated at the end) is accepted. Either
winding produces the same roof. Collinear vertices that still enclose area
are roofed; they are the same building with an extra point on an eave.
Units on the returned roof are metres and degrees.

## Worked numbers

A 10 m square at 45° has apex height 5 m and four faces of 25 m² plan /
`25 / cos(45°)` sloped. A 10 x 6 m rectangle at 45° has a 4 m ridge at
height 3 m, from `(3, 3, 3)` to `(7, 3, 3)`.

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

`tests/test_invariants.py` generates convex footprints and asserts the terrain
invariants (areas, planarity, drainage, arc labels, determinism). Later
geometry tickets widen `tests/generation.py` rather than copying those
assertions.

## Glossary

Terms (`footprint`, `face`, `pitch`, `plan area`, `sloped area`, `ridge`,
`hip`, `eave`) are defined in [`CONTEXT.md`](CONTEXT.md). The algorithm
choice is recorded in [`docs/adr/0001-own-weighted-straight-skeleton-in-python.md`](docs/adr/0001-own-weighted-straight-skeleton-in-python.md).
