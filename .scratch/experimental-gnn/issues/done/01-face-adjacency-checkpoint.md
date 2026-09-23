# 01: Train and ship the face-adjacency checkpoint

**What to build:** Someone reproducing the fit runs one command. It fetches the published outline and face-adjacency pairs from Ren et al. 2021 (RoofSynthesis raw data, 2539 roofs, CC BY-NC 4.0), trains the face-adjacency network specified in their supplement (appendix B.2), and writes a checkpoint this repo commits. The page does not do this. The skeleton is untouched.

The network is not the outline transformer from the same paper. Four blocks use the published widths. Each block updates an adjacency feature, an edge feature, and a global feature, except the last block, which updates adjacency only. A linear layer turns the last adjacency feature into a logit. The loss is binary cross-entropy against the labelled pairs. The initial edge feature is the midpoint, the inward unit normal, and the length, after the vertices are centred and scaled isotropically into [-1, 1]. Training augments with a random rotation and a scale in [0.8, 1.2]. The supplement initialises the adjacency and global features with zeros and never states their width: they are width 0, so the first block concatenates nothing extra. Each MLP is a linear layer, a ReLU, and a linear layer.

The published train/test membership was not released. Sort by name, hold out 239, then drop 4-vertex footprints from both sides. Learning rate, batch size, and epoch count were not published for this network. Choose them so the held-out intersection-over-union is in the neighbourhood of the paper's 97.30% on their unreleased split. Record the number this split actually reaches. Do not claim their figure.

The downloaded pairs stay out of git. `import krovlab` still pulls in no third-party packages. PyTorch is an extra, imported only by this fit.

**Blocked by:** None (can start immediately)

**Status:** done

**Stories:** 28, 29, 30, 31, 32

**Prior art:** ADR-0001 (the core stays dependency-free). PRD "Implementation Decisions" on the architecture, the width-0 initial features, the split, and the unpublished hyperparameters. The single-footprint tests never import a third-party package through `import krovlab`.

**Artifact homes:** Checkpoint `models/ren2021-face-adjacency.pt` (tracked). Held-out intersection-over-union, learning rate, batch size, and epoch count in `models/ren2021-face-adjacency.md` (tracked). Pairs under `data/ren2021/`, which this ticket gitignores. Neither model path is ignored today.

- [x] One command fetches the pairs and trains the supplement's face-adjacency network
- [x] The pairs under `data/ren2021/` are gitignored and are not committed
- [x] `models/ren2021-face-adjacency.pt` is the committed checkpoint
- [x] `models/ren2021-face-adjacency.md` records the held-out intersection-over-union and the learning rate, batch size, and epoch count that produced it
- [x] The held-out count is 239 footprints by sorted name, then 4-vertex footprints dropped
- [x] A synthetic labelled footprint can be memorised, and the probability that edge i meets edge j equals the probability that j meets i
- [x] `import krovlab` still imports no third-party package
