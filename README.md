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
    print(result.reason)
else:
    print(result.ridge_height)       # 3.0 m
    print(result.total_sloped_area)  # covering area, m²
```

`roof` is the only entry point. Everything else — the wavefront, the event
queue, the conversion of pitch to weight — stays behind it.

### Pitch

Pitch is the angle from horizontal in degrees. It must satisfy
`0 < pitch <= 90`. Outside that range you get a `Failure`, not an exception.

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

Each face also splits area in two: `plan_area` (horizontal projection) and
`sloped_area` (`plan_area / cos(pitch)`). Plan areas sum to the footprint area.

`Face.edge_index` `i` is the edge from `footprint[i]` to
`footprint[(i + 1) % n]`, even if you passed the ring clockwise.

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

## Glossary

Terms (`footprint`, `face`, `pitch`, `plan area`, `sloped area`, `ridge`,
`hip`, `eave`) are defined in [`CONTEXT.md`](CONTEXT.md). The algorithm
choice is recorded in [`docs/adr/0001-own-weighted-straight-skeleton-in-python.md`](docs/adr/0001-own-weighted-straight-skeleton-in-python.md).
