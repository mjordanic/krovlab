"""Fetch and split the published Ren et al. 2021 outline / adjacency pairs.

Pairs live under ``data/ren2021/`` and stay out of git. This module does
not import PyTorch.
"""

from __future__ import annotations

import tarfile
import urllib.request
from collections.abc import Sequence
from pathlib import Path

DATASET_URL = "https://codeload.github.com/llorz/SGA21_roofOptimization/tar.gz/main"
N_PUBLISHED = 2539
HOLD_OUT = 239
type Vertex = tuple[float, float]
type Pair = tuple[str, list[Vertex], list[list[int]]]


def split_by_sorted_name(
    names: Sequence[str], *, hold_out: int = HOLD_OUT
) -> tuple[list[str], list[str]]:
    """Hold out the last ``hold_out`` names after sorting."""
    ordered = sorted(names)
    return ordered[:-hold_out], ordered[-hold_out:]


def drop_four_vertex(pairs: Sequence[Pair]) -> list[Pair]:
    """Drop footprints with exactly four vertices."""
    return [pair for pair in pairs if len(pair[1]) != 4]


def parse_outline(text: str) -> list[Vertex]:
    vertices: list[Vertex] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        x_str, y_str = line.split(",")
        vertices.append((float(x_str), float(y_str)))
    return vertices


def parse_adjacency(text: str, n: int) -> list[list[int]]:
    labels = [[0] * n for _ in range(n)]
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        i_str, j_str = line.split(",")
        i = int(i_str) - 1
        j = int(j_str) - 1
        labels[i][j] = 1
        labels[j][i] = 1
    return labels


def fetch_pairs(dest: Path) -> None:
    """Download RoofSynthesis raw pairs into ``dest`` if not already complete."""
    dest.mkdir(parents=True, exist_ok=True)
    if (
        len(list(dest.glob("*.outline"))) == N_PUBLISHED
        and len(list(dest.glob("*.adjacency"))) == N_PUBLISHED
    ):
        return
    request = urllib.request.Request(
        DATASET_URL, headers={"User-Agent": "krovlab-ren-gnn"}
    )
    with (
        urllib.request.urlopen(request) as response,
        tarfile.open(fileobj=response, mode="r|gz") as archive,
    ):
        for member in archive:
            if not member.isfile():
                continue
            name = member.name
            if "/RoofSynthesis/data/raw/" not in name:
                continue
            if not (name.endswith(".outline") or name.endswith(".adjacency")):
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            (dest / Path(name).name).write_bytes(extracted.read())


def load_pairs(dest: Path) -> list[Pair]:
    pairs: list[Pair] = []
    for outline_path in sorted(dest.glob("*.outline")):
        name = outline_path.name
        vertices = parse_outline(outline_path.read_text())
        adj_path = dest / outline_path.with_suffix(".adjacency").name
        labels = parse_adjacency(adj_path.read_text(), len(vertices))
        pairs.append((name, vertices, labels))
    return pairs


def train_and_held_out(dest: Path) -> tuple[list[Pair], list[Pair]]:
    pairs = load_pairs(dest)
    names = [name for name, _, _ in pairs]
    train_names, held_names = split_by_sorted_name(names)
    by_name = {name: pair for name, pair in zip(names, pairs, strict=True)}
    train = drop_four_vertex([by_name[name] for name in train_names])
    held = drop_four_vertex([by_name[name] for name in held_names])
    return train, held
