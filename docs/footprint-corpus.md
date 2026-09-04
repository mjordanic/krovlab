# Footprint corpus

These fixtures are stand-ins from the library's worked examples, not yet sourced from the architect's recent projects.

The corpus covers 8 footprints.

**Pass rate: 7/7** (100%) of fixtures expected to produce a roof produced a valid terrain.

1 fixture recorded as unroofable (expected failure), counted separately from an invariant failure.

| Fixture | Outcome | Detail |
| --- | --- | --- |
| `bowtie` | expected failure | self_intersection |
| `courtyard` | pass | topology hash `dfa9660e9c5ccdfcdb7832f6c18baa0e8af97da0b4f58530f32669de8ea48534` |
| `l-shape-overhang` | pass | topology hash `881c6d116216f0ff74ef26dfcf2abe07d65a89f01bb4ddeb3adf7fb01ad3f781` |
| `l-shape` | pass | topology hash `881c6d116216f0ff74ef26dfcf2abe07d65a89f01bb4ddeb3adf7fb01ad3f781` |
| `rectangle-10x6` | pass | topology hash `088246302c173f1a7e33044bf3d79b0379e955c6d371734e4676adab81ba7aa0` |
| `rectangle-gabled` | pass | topology hash `f36128464c6da2d8f4c82e3f4e874bd92308c6dfb4bfd2149acc169704e817b8` |
| `square-10m` | pass | topology hash `fd7abc2a1674ecf1dba62fbd03e05db4025cc894278e811894b7d863ec249591` |
| `u-shape` | pass | topology hash `b90bc9539bda70808256dd58116540bda78f8e028916f0d43fe2d6e7aab568cc` |

## Expected unroofable

- `bowtie`: `self_intersection` — footprint is self-intersecting
