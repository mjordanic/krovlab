"""Fetch the published pairs and train the face-adjacency network.

Run from the repo root::

    uv run --extra gnn python -m krovlab.ren_gnn
"""

from __future__ import annotations

import random
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import Tensor

from krovlab.ren_gnn.data import (
    HOLD_OUT,
    N_PUBLISHED,
    Pair,
    fetch_pairs,
    train_and_held_out,
)
from krovlab.ren_gnn.geometry import centre_and_scale, random_rotation_and_scale
from krovlab.ren_gnn.model import FaceAdjacencyNet

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "ren2021"
CHECKPOINT = REPO_ROOT / "models" / "ren2021-face-adjacency.pt"
CHECKPOINT_NOTES = REPO_ROOT / "models" / "ren2021-face-adjacency.md"

LEARNING_RATE = 1e-3
BATCH_SIZE = 8
EPOCHS = 80
SEED = 0


def _device() -> torch.device:
    # Tiny per-roof graphs are faster on CPU than on MPS kernel launches.
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _prepared(vertices: list[tuple[float, float]], *, augment: bool) -> Tensor:
    tensor = torch.tensor(vertices, dtype=torch.float32)
    tensor = centre_and_scale(tensor)
    if augment:
        tensor = random_rotation_and_scale(tensor)
    return tensor


def _off_diag(n: int, device: torch.device) -> Tensor:
    return ~torch.eye(n, dtype=torch.bool, device=device)


def _loss(model: FaceAdjacencyNet, vertices: Tensor, labels: Tensor) -> Tensor:
    logits = model(vertices)
    mask = _off_diag(vertices.size(0), vertices.device)
    return F.binary_cross_entropy_with_logits(logits[mask], labels[mask])


def _iou(pred: Tensor, labels: Tensor) -> float:
    n = pred.size(0)
    upper = torch.triu(
        torch.ones(n, n, dtype=torch.bool, device=pred.device), diagonal=1
    )
    predicted = pred[upper]
    target = labels[upper].bool()
    inter = int((predicted & target).sum().item())
    union = int((predicted | target).sum().item())
    if union == 0:
        return 1.0
    return inter / union


def _held_out_iou(
    model: FaceAdjacencyNet, held: list[Pair], device: torch.device
) -> float:
    model.eval()
    scores: list[float] = []
    with torch.no_grad():
        for _, vertices, labels in held:
            prepared = _prepared(vertices, augment=False).to(device)
            labels_t = torch.tensor(labels, dtype=torch.float32, device=device)
            pred = torch.sigmoid(model(prepared)) > 0.5
            scores.append(_iou(pred, labels_t))
    return sum(scores) / len(scores)


def main() -> None:
    random.seed(SEED)
    torch.manual_seed(SEED)
    fetch_pairs(DATA_DIR)
    train, held = train_and_held_out(DATA_DIR)
    device = _device()
    model = FaceAdjacencyNet().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    for epoch in range(EPOCHS):
        model.train()
        order = list(range(len(train)))
        random.shuffle(order)
        running = 0.0
        optimizer.zero_grad()
        for step, index in enumerate(order, start=1):
            _, vertices, labels = train[index]
            prepared = _prepared(vertices, augment=True).to(device)
            labels_t = torch.tensor(labels, dtype=torch.float32, device=device)
            loss = _loss(model, prepared, labels_t) / BATCH_SIZE
            loss.backward()  # type: ignore[no-untyped-call]
            running += float(loss.item()) * BATCH_SIZE
            if step % BATCH_SIZE == 0 or step == len(order):
                optimizer.step()
                optimizer.zero_grad()
        score = _held_out_iou(model, held, device)
        mean_loss = running / len(train)
        print(
            f"epoch {epoch + 1}/{EPOCHS}  loss {mean_loss:.4f}  "
            f"held-out IoU {score:.4f}",
            flush=True,
        )

    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    model.cpu()
    torch.save(model.state_dict(), CHECKPOINT)
    score = _held_out_iou(model.to(device), held, device)
    percent = 100.0 * score
    CHECKPOINT_NOTES.write_text(
        "\n".join(
            [
                "# Ren et al. 2021 face-adjacency checkpoint",
                "",
                f"Held-out intersection-over-union: {percent:.2f}%",
                "",
                "This is the score on this repository's split, not the paper's",
                "97.30% on their unreleased split. The neighbourhood of 97.30%",
                "is what training aimed at.",
                "",
                f"Split: {N_PUBLISHED} roofs sorted by name, last {HOLD_OUT}",
                "held out, then 4-vertex footprints dropped from both sides.",
                f"Train roofs after the drop: {len(train)}.",
                f"Held-out roofs after the drop: {len(held)}.",
                "",
                f"Learning rate: {LEARNING_RATE}",
                f"Batch size: {BATCH_SIZE}",
                f"Epochs: {EPOCHS}",
                "",
                "Pairs: RoofSynthesis raw data of llorz/SGA21_roofOptimization,",
                "CC BY-NC 4.0. Fetched by",
                "`uv run --extra gnn python -m krovlab.ren_gnn`.",
                "",
            ]
        )
        + "\n"
    )
    print(f"wrote {CHECKPOINT}  held-out IoU {percent:.2f}%", flush=True)


if __name__ == "__main__":
    main()
