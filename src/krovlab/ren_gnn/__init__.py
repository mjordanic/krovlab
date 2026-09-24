"""Optional face-adjacency network. Install the ``gnn`` extra to use it.

The core package does not import this module. PyTorch is loaded only here.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

try:
    import torch
    import torch.nn.functional as F
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "krovlab.ren_gnn requires the gnn extra. Install with: uv sync --extra gnn"
    ) from exc

from krovlab.ren_gnn.geometry import centre_and_scale
from krovlab.ren_gnn.model import FaceAdjacencyNet

type Footprint = Sequence[tuple[float, float]]
type MeetLabels = Sequence[Sequence[int]]


def load_face_adjacency_net(path: str | Path) -> FaceAdjacencyNet:
    """Load face-adjacency weights. Eval mode, on CPU."""
    model = FaceAdjacencyNet()
    state = torch.load(path, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model


def pairwise_meet_probability(
    footprint: Footprint, model: FaceAdjacencyNet
) -> list[list[float]]:
    """Return P(wall i meets wall j) as a symmetric n-by-n matrix."""
    device = next(model.parameters()).device
    vertices = centre_and_scale(
        torch.tensor(footprint, dtype=torch.float32, device=device)
    )
    model.eval()
    with torch.no_grad():
        probs = torch.sigmoid(model(vertices))
        probs = 0.5 * (probs + probs.T)
    return probs.tolist()


def fit(
    model: FaceAdjacencyNet,
    footprint: Footprint,
    labels: MeetLabels,
    *,
    steps: int,
    lr: float,
) -> None:
    """Train ``model`` to recover ``labels`` on one footprint."""
    device = next(model.parameters()).device
    vertices = centre_and_scale(
        torch.tensor(footprint, dtype=torch.float32, device=device)
    )
    target = torch.tensor(labels, dtype=torch.float32, device=device)
    n = vertices.size(0)
    off_diag = ~torch.eye(n, dtype=torch.bool, device=device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()
    for _ in range(steps):
        optimizer.zero_grad()
        logits = model(vertices)
        loss = F.binary_cross_entropy_with_logits(logits[off_diag], target[off_diag])
        loss.backward()  # type: ignore[no-untyped-call]
        optimizer.step()


__all__ = [
    "FaceAdjacencyNet",
    "fit",
    "load_face_adjacency_net",
    "pairwise_meet_probability",
]
