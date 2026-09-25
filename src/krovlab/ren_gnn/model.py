"""Face-adjacency network from Ren et al. 2021, supplement appendix B.2.

Four blocks at the published widths. Each block updates an adjacency
feature, an edge feature, and a global feature, except the last block,
which updates adjacency only. A linear layer turns the last adjacency
feature into a logit. Initial adjacency and global features are width 0.
Each MLP is a linear layer, a ReLU, and a linear layer.
"""

from __future__ import annotations

from typing import cast

import torch
from torch import Tensor, nn

from krovlab.ren_gnn.geometry import edge_features


def _mlp(in_dim: int, hidden: int, out_dim: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Linear(in_dim, hidden),
        nn.ReLU(),
        nn.Linear(hidden, out_dim),
    )


def _cat(*parts: Tensor) -> Tensor:
    nonempty = [p for p in parts if p.size(-1) > 0]
    return torch.cat(nonempty, dim=-1)


class FaceAdjacencyNet(nn.Module):
    """Predict a logit that wall i meets wall j for every pair of walls."""

    def __init__(self) -> None:
        super().__init__()
        e_dim, a_dim, g_dim = 5, 0, 0
        self.adj_mlps = nn.ModuleList()
        self.edge_mlps = nn.ModuleList()
        self.global_mlps = nn.ModuleList()
        blocks: list[
            tuple[tuple[int, int], tuple[int, int] | None, tuple[int, int] | None]
        ] = [
            ((32, 32), (64, 32), (64, 32)),
            ((96, 64), (96, 64), (96, 64)),
            ((192, 128), (192, 128), (192, 128)),
            ((512, 256), None, None),
        ]
        for adj_hw, edge_hw, glob_hw in blocks:
            adj_in = e_dim + a_dim + g_dim
            self.adj_mlps.append(_mlp(adj_in, adj_hw[0], adj_hw[1]))
            a_dim = adj_hw[1]
            if edge_hw is None or glob_hw is None:
                break
            edge_in = a_dim + e_dim + g_dim
            self.edge_mlps.append(_mlp(edge_in, edge_hw[0], edge_hw[1]))
            e_dim = edge_hw[1]
            glob_in = e_dim + g_dim
            self.global_mlps.append(_mlp(glob_in, glob_hw[0], glob_hw[1]))
            g_dim = glob_hw[1]
        self.logit = nn.Linear(a_dim, 1)

    def forward(self, vertices: Tensor) -> Tensor:
        """Return an (N, N) logit matrix for prepared (N, 2) vertices."""
        edge = edge_features(vertices)
        n = edge.size(0)
        adj = edge.new_zeros(n, n, 0)
        glob = edge.new_zeros(0)
        n_adj = len(self.adj_mlps)
        for i, adj_mlp in enumerate(self.adj_mlps):
            max_e = torch.maximum(edge[:, None, :], edge[None, :, :])
            glob_pairs = glob.view(1, 1, -1).expand(n, n, -1)
            adj = adj_mlp(_cat(max_e, adj, glob_pairs))
            if i == n_adj - 1:
                break
            eye = torch.eye(n, dtype=torch.bool, device=edge.device)
            mean_adj = adj.masked_fill(eye[:, :, None], 0.0).sum(dim=1) / (n - 1)
            glob_edges = glob.view(1, -1).expand(n, -1)
            edge = self.edge_mlps[i](_cat(mean_adj, edge, glob_edges))
            mean_edge = edge.mean(dim=0)
            glob = self.global_mlps[i](_cat(mean_edge, glob))
        return cast(Tensor, self.logit(adj).squeeze(-1))
