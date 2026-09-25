"""Vertex prep and edge features for the face-adjacency network.

Vertices are centred and scaled isotropically into [-1, 1] before the
edge feature is built. The feature is midpoint, inward unit normal, and
length.
"""

from __future__ import annotations

import math

import torch
from torch import Tensor


def centre_and_scale(vertices: Tensor) -> Tensor:
    """Centre on the centroid and scale isotropically into [-1, 1]."""
    centred = vertices - vertices.mean(dim=0)
    extent = centred.abs().max().clamp(min=1e-12)
    return centred / extent


def random_rotation_and_scale(vertices: Tensor) -> Tensor:
    """Rotate by a uniform angle and scale by a factor in [0.8, 1.2]."""
    theta = torch.rand((), device=vertices.device, dtype=vertices.dtype) * (2 * math.pi)
    cos_t = torch.cos(theta)
    sin_t = torch.sin(theta)
    rotated = torch.stack(
        (
            vertices[:, 0] * cos_t - vertices[:, 1] * sin_t,
            vertices[:, 0] * sin_t + vertices[:, 1] * cos_t,
        ),
        dim=-1,
    )
    scale = 0.8 + 0.4 * torch.rand((), device=vertices.device, dtype=vertices.dtype)
    return rotated * scale


def edge_features(vertices: Tensor) -> Tensor:
    """Return an (N, 5) tensor: midpoint (2), inward unit normal (2), length."""
    nxt = torch.roll(vertices, -1, dims=0)
    vec = nxt - vertices
    length = vec.norm(dim=-1, keepdim=True).clamp(min=1e-12)
    midpoint = 0.5 * (vertices + nxt)
    # Rotate the edge 90° counter-clockwise: interior is to the left of a
    # counter-clockwise ring, so this is the inward normal. Flip if clockwise.
    rotated = torch.stack((-vec[:, 1], vec[:, 0]), dim=-1)
    area2 = (vertices[:, 0] * nxt[:, 1] - nxt[:, 0] * vertices[:, 1]).sum()
    sign = torch.where(area2 >= 0, length.new_ones(()), -length.new_ones(()))
    normal = rotated / length * sign
    return torch.cat((midpoint, normal, length), dim=-1)
