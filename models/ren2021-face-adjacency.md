# Ren et al. 2021 face-adjacency checkpoint

Held-out intersection-over-union: 98.31%

This is the score on this repository's split, not the paper's
97.30% on their unreleased split. The neighbourhood of 97.30%
is what training aimed at.

Split: 2539 roofs sorted by name, last 239
held out, then 4-vertex footprints dropped from both sides.
Train roofs after the drop: 1903.
Held-out roofs after the drop: 202.

Learning rate: 0.001
Batch size: 8
Epochs: 80

Pairs: RoofSynthesis raw data of llorz/SGA21_roofOptimization,
CC BY-NC 4.0. Fetched by
`uv run --extra gnn python -m krovlab.ren_gnn`.

