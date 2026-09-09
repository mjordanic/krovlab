# Graph / GNN alternatives to the straight skeleton

Status: ideation. Not a design decision and not a spec.
Branch: `GNN-alternative`.
Date: 2026-09-05.

This note records a literature review of planar-roof construction
*without* (or beyond) the straight skeleton, and then asks a narrower
question that the papers mostly do not:

> An architect gives a **footprint** (the closed polygon in plan) and a
> **pitch per face** (angle from horizontal, in degrees). Can a graph
> model — possibly a GNN — return hips, valleys, ridges and verges that
> respect those pitches, including roofs the weighted straight skeleton
> cannot represent?

Pitch is defined in [`CONTEXT.md`](../CONTEXT.md). Limits of the
skeleton we already ship are in [`limitations.md`](limitations.md).
Why we implemented a weighted straight skeleton in-house is in
[ADR 0001](adr/0001-own-weighted-straight-skeleton-in-python.md).

Claims below are tied to a source. Where a paper is silent on pitch,
that silence is stated rather than inferred into a capability.

---

## 1. The product problem (what we actually want)

**Inputs the architect controls**

- Footprint: a simple polygon in metres, possibly with holes.
  Counter-clockwise, as in `CONTEXT.md`.
- Pitch per face. Today that is one number per footprint *edge*,
  because krovlab gives each non-gabled edge exactly one face.
  `pitch = 90` is a gable: no face over that edge.
- Optionally: overhang, which is an offset of the footprint, not a
  different roof algorithm.

**Outputs that have to be construction-valid**

- A planar 3D roof that is a *terrain* (one height per plan point).
- Labels on the interior arcs: ridge, hip, valley, verge.
- Quantities: sloped area, linear metres by type.

That is a **design** problem. Most of the learning papers below are
**reconstruction** problems (image or LiDAR in, a roof that matches the
observation out). They do not take pitch as a design variable.
`Point2WSS` is the exception that still uses a skeleton: it *predicts*
pitches from a point cloud, then runs a weighted straight skeleton
(Queffélec et al. 2026). We want the opposite direction: pitches are
given, topology may need to be chosen.

---

## 2. Why the skeleton is both the right tool and the wrong ceiling

Aichholzer, Aurenhammer, Alberts and Gärtner introduced the straight
skeleton as a *roof*: each footprint edge supports a plane, the planes
rise together, and the arrangement is a terrain (Aichholzer et al. 1995;
Aichholzer and Aurenhammer 1996). Time of the inward wavefront *is*
height. For a simple polygon the skeleton is a tree; its arcs are the
hips, valleys and ridges.

The **weighted** straight skeleton lets each edge move at its own speed
(Eppstein and Erickson 1999; Biedl et al. 2015). In this project,
`weight = cot(pitch)`, so a different pitch per edge is exactly a
weighted skeleton. Kelly and Wonka (2011) used that parameterisation
for interactive building modelling. Held and Palfrader (2017) added
*additive* weights (a delay before an edge starts moving) for
half-hips, knee-walls, and ridges perpendicular to a long wall.

Three facts follow, and they decide whether a GNN has anything to do.

1. **If every outline edge owns exactly one planar face at a given
   pitch, the interior graph is determined** (when the weighted
   skeleton is unique). A network that “finds the other nodes” in that
   regime is approximating an algorithm. krovlab already *is* that
   algorithm.
2. **The map from footprint to topology is not injective.** The same
   outline admits several valid roofs. The skeleton returns one of
   them. Ren et al. (2021, §3.4, Fig. 9) show four different dual
   graphs on one outline. Our [`limitations.md`](limitations.md)
   records the same limit.
3. **Some buildable roofs are outside the skeleton’s class.** A face
   that spans several outline edges cannot occur (Ren et al. 2021,
   Fig. 3; [`limitations.md`](limitations.md)). The skeleton also
   invents extra vertices that a carpenter would not draw (Ren et al.
   2021, Fig. 2).

A graph/GNN method is only a *design* alternative where (2) or (3)
matter: the architect wants a style the skeleton will not emit, or a
face layout the skeleton cannot represent, *while still honouring the
pitches they typed*.

Where (1) holds, keep the skeleton.

---

## 3. Literature, grouped by what it replaces

Each subsection is a summary of what the paper *does*, what it takes as
input, and whether pitch appears. Papers that only reconstruct from
images or points are included because they use the same graph objects,
not because they solve the design problem.

### 3.1 The skeleton family (geometry engines, not learned)

| Work | What it is | Pitch? |
|---|---|---|
| Aichholzer et al. 1995; Aichholzer and Aurenhammer 1996 | Unweighted straight skeleton; roof = wavefront × time | Uniform. All faces the same pitch. |
| Eppstein and Erickson 1999 | Motorcycle graphs; weighted skeleton as raising roofs | Yes: per-edge speed / slope. |
| Felkel and Obdržálek 1998 | Practical wavefront implementation (the formulation ADR 0001 adopted) | Unweighted in that paper. |
| Biedl, Held, Huber, Kaaser, Palfrader 2015 | Weighted skeletons of simple polygons may contain cycles and crossings; positive multiplicative weights behave like the unweighted case | Yes: multiplicative weights. |
| Kelly and Wonka 2011 | Interactive procedural extrusions of whole buildings on a weighted skeleton | Yes: per-edge weights in a GUI. |
| Held and Palfrader 2017 | Additive + multiplicative weights. Delayed wavefront motion. Gables without post-processing; ridges perpendicular to long walls | Yes: multiplicative (pitch) and additive (start height). |
| Huber and Held 2012 | Fast skeleton via generalised motorcycle graphs (`Bone`) | Implementation of the unweighted (and related) skeleton, not a different roof model. |

**Medial axis / Voronoi** is the usual alternative *skeleton*, not an
alternative *roof*. It produces curves (parabolic arcs at reflex
vertices). Tiled roofs need planar faces, so it is the wrong object
(Aichholzer et al. motivated the straight skeleton on exactly this
ground).

**Motorcycle graphs** are a computational reduction *to* the skeleton
(Eppstein and Erickson 1999; Cheng and Vigneron; Huber and Held 2012).
Same roof, different algorithm.

### 3.2 Roof graph + planarity optimisation — Ren et al. 2021

**Jing Ren, Biao Zhang, Bojian Wu, Jianqiang Huang, Lubin Fan,
Maks Ovsjanikov, Peter Wonka.**
“Intuitive and Efficient Roof Modeling for Reconstruction and Synthesis.”
*ACM Transactions on Graphics* 40(6), SIGGRAPH Asia 2021.
DOI: [10.1145/3478513.3480494](https://doi.org/10.1145/3478513.3480494).
arXiv: [2109.07683](https://arxiv.org/abs/2109.07683).
Code: [llorz/SGA21_roofOptimization](https://github.com/llorz/SGA21_roofOptimization).

This is the paper to treat as the baseline for a graph alternative,
not as a side citation.

**Representation.** A *roof graph* \(G=(V,E)\) in plan:

- Outline vertices \(V_{\mathcal{O}}\) and outline edges \(E_{\mathcal{O}}\)
  (the footprint).
- Roof (interior) vertices \(V_{\mathcal{R}}\) and roof edges \(E_{\mathcal{R}}\)
  (ridges, hips, valleys, and any extra structure).
- Faces \(F\) of the embedding are the roof faces.

Equivalently, a *dual graph*: one node per face, adjacency matrix
\(A^{\mathcal{D}}\). Adding an “outside” node and dualising recovers the
primal (their Fig. 7). If each face stems from one outline edge, the
dual’s node set is *fixed* (size \(n\) = number of eaves). Predicting
topology then reduces to predicting which faces are adjacent. Merged
faces (one plane over several eaves) are expressed by merging rows of
\(A^{\mathcal{D}}\) (their Fig. 15). That is exactly the skeleton’s
missing case.

**Validity.** A 3D embedding is valid if every face is planar and the
roof has non-zero height (Def. 3.1). A 2D embedding is valid if some
3D lifting of it is valid (Def. 3.2). Remark 3.1: for two adjacent
planar faces with fixed outline edges, the shared edge is either
parallel to both eaves or concurrent with them. That is the algebraic
content of “this interior graph is a roof.”

**Geometry, not pitch.** They minimise a planarity energy: the sum, over
faces, of the smallest eigenvalue of the face vertices’ covariance
(Eq. 1). For a user-drawn primal they add a data term that keeps the
2D layout near the drawing, and a hard constraint that one interior
vertex has height \(h\) (Eq. 2) so the flat roof is not a minimiser.
For a dual graph with no interior drawing they initialise by spectral
graph drawing with the outline fixed (Eq. 4) and add *aesthetic*
terms: angle bisectors at convex corners, and equal-offset (medial)
ridges between parallel eaves (Eq. 3). Those aesthetic terms are the
**unweighted**-skeleton prior. They are the wrong regulariser when
adjacent faces have different pitches: a weighted hip is a *weighted*
bisector, not an angle bisector, and a ridge between two pitches is
not midway.

They do **not** take per-face pitch as input. Height \(h\) is a single
scalar for the whole roof. Fig. 10 of their paper shows several valid
3D embeddings of the *same* outline and the *same* topology — which is
what you get when pitch is left free. In the conclusion they list
slope as future work, verbatim:

> It would also be interesting to study practical constraints for roof
> fabricability using our optimization-based formulation, such as
> incorporating slope requirements of roof faces during the
> construction, which can be addressed by either hard or soft
> constraints. (Ren et al. 2021, §7)

**Learning.** They separate discrete topology from continuous
embedding. A transformer generates outline vertex sequences. A graph
convolutional network (Kipf and Welling 2016 style; their §5)
predicts \(p_{ij}\), the probability that the face of eave \(i\) is
adjacent to the face of eave \(j\). Binary cross-entropy against
ground-truth dual adjacency. They then extract a dual graph and run
the planarity optimiser. The GCN sees the outline. It does not see
pitch.

**Dataset.** 2539 image–mesh pairs with planar polygonal roofs, used
both for the GCN and as a public resource. RoofDiT later trains on a
split of this set (1926 / 249 / 223; Panangian and Bittner 2026, §3).

**Compared to the skeleton.** On 16 aerial images, a user draws the
primal graph and their optimiser reconstructs a planar roof. The
straight skeleton and Kelly–Wonka weighted skeleton, given only the
same outline (and, for WSS, hand-tuned weights), leave structural
errors the weights cannot fix, because weights do not change
*topology* (their Table 2, Fig. 20). That is the right criticism of
the skeleton as a *reconstruction* tool. It is not a criticism of the
skeleton as a *design* tool when the architect *wants* those pitches
and that one-face-per-eave class.

### 3.3 RoofDiT — Panangian and Bittner 2026

**Daniel Panangian, Ksenia Bittner.**
“Diffusion Transformers for Roof Graph Synthesis and Reconstruction.”
arXiv: [2608.25652](https://arxiv.org/abs/2608.25652) (preprint).
German Aerospace Center (DLR).

**What it is.** A generative model over **2D** vertex–edge roof graphs
in top view. Two stages, following GSDiff (Hu et al. 2024): a
diffusion transformer denoises node coordinates; an edge module then
predicts connectivity.

**Conditioning, as stated.** Three modes (abstract and §4.2):

1. Unconditional (noise → graph).
2. Footprint-conditioned: footprint vertices are 2D geometric tokens,
   concatenated with the roof-node sequence, joint self-attention.
3. Image-guided: DINOv2 features via cross-attention. Can be combined
   with the footprint.

Pitch, slope, height, and 3D coordinates are **not** in the model.
Node state is \(X \in \mathbb{R}^{N \times d}\) with 2D coordinates and
a validity flag (§4.2). Their own limitations paragraph:

> The current model operates on planar roof graphs and does not
> directly recover full 3D geometry, roof heights, or watertight
> building models. (Panangian and Bittner 2026, §7)

“Planar rate” in their tables is **2D non-crossing** of edges, not 3D
face planarity (§5.3).

**Vs the skeleton.** On footprint-conditioned generation they compare
to a straight-skeleton baseline (Table 2). The skeleton wins on node
F1@5, face F1, matched IoU, planar rate (1.000 vs 0.873) and valid
rate (1.000 vs 0.841). RoofDiT wins on node-count MAE, face-count
error, edge F1, and best-of-5 face F1 / valid rate. They interpret
this as: the skeleton is a fixed procedural reading that over-partitions;
the diffusion model can match real ridge layouts and sample several
styles per footprint. Validity is learned, not guaranteed.

**Dataset.** Derived from Ren et al.’s annotations, canonicalised
(rotate longest eave to an axis; snap near-horizontal/vertical
segments). Footprint vertices are the exterior boundary of the union
of roof faces — so holes in the sense of courtyards are not an
input they describe.

**Pitch.** Not an input, not a loss, not an evaluation. The user’s
reading is correct: RoofDiT ignores pitch.

### 3.4 Other generative roof models

**Roof-GAN.** Yiming Qian, Hao Zhang, Yasutaka Furukawa, CVPR 2021,
pp. 2796–2805.
DOI: [10.1109/CVPR46437.2021.00282](https://doi.org/10.1109/CVPR46437.2021.00282).
[arXiv:2012.09340](https://arxiv.org/abs/2012.09340).
A roof is a graph of *primitives* (nodes) and pairwise *relations*
(edges). Node geometry is generated as raster maps that encode facet
segmentation **and angles**, then vectorised. Those angles are an
*output of the generator*, not an architect-specified pitch per
footprint edge. The model is a prior over residential primitive
arrangements, not a map from footprint + pitch to a terrain.

**Loops2Roofs.** Jianwei Guo, Pu Li, Qi Zeng, Wenhao Zhang, Pengxu Li,
Liangliang Nan, Bedřich Beneš, Dong-Ming Yan.
*ACM Transactions on Graphics*, 2026.
DOI: [10.1145/3807955](https://doi.org/10.1145/3807955).
Each roof face is a 3D polygonal *loop*. A transformer diffusion
model denoises 3D vertex coordinates, conditioned on structural
priors (number of faces, vertices per face) from an autoregressive
model; a neural stitching module recovers incidence between loops.
Optionally, 2D footprints for image-conditioned generation. The
published method description does **not** list per-face pitch as an
input. Unlike RoofDiT it *does* emit 3D meshes, so pitches exist as
a *consequence* of the generated planes — they are not specified
up front.

### 3.5 Learning that still uses a skeleton

**Point2WSS.** Queffélec, Trouvé, Roussel, Wu, Vallet.
ISPRS Annals XI-2-2026, 331–340.
DOI: [10.5194/isprs-annals-XI-2-2026-331-2026](https://doi.org/10.5194/isprs-annals-XI-2-2026-331-2026).
Code: [KWIKERRR/point2wss](https://github.com/KWIKERRR/point2wss).

A parametric building: footprint + one slope per edge + a height,
then a weighted straight skeleton, then wall extrusion. A multimodal
network predicts those continuous parameters from aerial LiDAR. This
is the same parameterisation krovlab uses, in the *reconstruction*
direction. It does not expand the skeleton’s topological class. It
is useful as evidence that “footprint + per-edge slope → mesh” is
already considered a complete parametric model in 2026 photogrammetry.

### 3.6 Dual roof-topology graphs from photogrammetry

These papers work with the *dual* of a roof (a node per observed
plane, an edge if two planes meet). They start from LiDAR or imagery,
not from a footprint the architect drew.

- Verma, Thies, Bolles, and later **roof topology graphs (RTG)**:
  Oude Elberink and Vosselman; Xiong, Oude Elberink and Vosselman,
  “A graph edit dictionary for correcting errors in roof topology
  graphs reconstructed from point clouds,” *ISPRS Journal of
  Photogrammetry and Remote Sensing* 93:227–242, 2014.
  Typical errors in the dual are repeating; a dictionary of graph
  edits corrects them. Subgraph vocabulary: loose node, loose edge,
  independent cycle — independent face, ridge, corner.
- Xu, Shen, Persson 2016: global graph-cut instead of local edits.
- **RSGNN.** Zhao, Persello, Stein,
  *ISPRS Journal of Photogrammetry and Remote Sensing* 187:34–45, 2022.
  Multi-task primitive extraction from VHR images plus a GNN relation
  module to assemble a planar roofline graph. Input: image. Not pitch.
- **PolyRoof / Re:PolyWorld.** Amrullah, Panangian, Bittner, JURSE 2025;
  Zorzi et al., PolyWorld, CVPR 2022. Vertices + GNN edges from
  imagery, for polygonisation.

Useful as a vocabulary for what a dual GNN must be allowed to emit.
They do not take design pitches.

### 3.7 Plane arrangements (need planes, not just a polygon)

- **PolyFit.** Nan and Wonka, ICCV 2017. Intersect candidate planes,
  pick a manifold subset by integer programming.
- **Kinetic shape reconstruction.** Bauchet and Lafarge, *ACM TOG*
  39(5), 2020. Planes grow until they collide; min-cut extracts a
  mesh. Now in CGAL as Kinetic Surface Reconstruction.

These reconstruct from detected planes (usually LiDAR). Without a
point cloud there are no planes to arrange, unless you *create* one
plane per eave from the architect’s pitch — which is again the
weighted skeleton.

### 3.8 Procedural primitives and grammars

Müller, Wonka, Haegler, Ulmer, Van Gool, “Procedural modeling of
buildings,” SIGGRAPH 2006 (CGA / CityEngine). Buron, Marvie, Gautron,
“GPU Roof Grammars,” Eurographics Short Papers 2013. Model-driven
photogrammetry (primitive libraries assembled from RTG subgraphs;
Xiong et al. 2013/2014).

An L-shape is two hip blocks, not a wavefront. Style is a rule.
There is no single well-defined roof for an arbitrary polygon, which
is why skeleton methods exist.

---

## 4. Can we modify RoofDiT to condition on pitch?

**Architecturally, yes. As a design tool, not by itself.**

### 4.1 What would change in their pipeline

Their footprint-conditioned node generator already treats footprint
vertices as tokens in the same space as interior vertices, with
relative geometry \((\Delta x, \Delta y, r, u_x, u_y)\) in attention
(Panangian and Bittner 2026, §4.2, Eqs. 1–2). Pitch is a scalar per
*eave*, i.e. per consecutive pair of footprint vertices (or per face,
if faces can span eaves).

A minimal modification that stays inside their framework:

1. Attach a pitch feature to each footprint token, for example
   \((\theta_i, \mathbf{1}_{\text{gable}})\) with \(\theta\) in degrees
   as krovlab stores it, gable = 90° / no face.
2. Keep the diffusion transformer and the edge head.
3. Train with pairs \((\text{footprint}, \boldsymbol{\theta}, G_{2D})\).

Nothing in the architecture forbids that. Conditioning of this shape
is how they already add the footprint; pitch would be extra channels
on those tokens, or a second token sequence of the same length.

### 4.2 Why that is not enough for this product

- The model still emits a **2D** graph. Pitch would influence *where
  nodes sit in plan* only if the training data couples pitch to
  layout (as the weighted skeleton does: a steeper face eats more plan
  width). It would not assign heights, would not enforce
  `plan_area / cos(pitch)` sloped area, and would not certify a
  terrain.
- Their alignment regulariser (horizontal, vertical, and the two
  diagonal families, Eq. 3) is a Manhattan/diagonal prior on 2D
  drawings. It is unrelated to pitch and can fight a weighted layout
  whose hips are not at 45°.
- Validity is still statistical (valid rate 0.841 on a single sample
  in the footprint-conditioned setting, Table 2). An architect’s tool
  cannot ship a 16% chance of a crossing graph.
- There is **no published training set** of (footprint, per-edge
  pitch, roof graph). Ren’s meshes *imply* pitches (each planar face
  has a measurable angle with the horizontal), but those pitches were
  never used as inputs. RoofDiT’s split does not include them.

### 4.3 If we did it anyway, what data?

Two honest datasets, with opposite meanings:

**A. Synthetic skeleton data.** Run krovlab (or any WSS) on many
footprints with random admissible pitches. Label = the skeleton
graph. A pitch-conditioned RoofDiT would be trained to imitate the
skeleton. That can be a regression test (“does the net reproduce WSS
on held-out polygons?”). It is not a new roof model. Do not publish
it as one.

**B. Measured pitches on real roofs.** Take Ren’s 2539 planar meshes.
For each face, compute pitch from the face normal. Associate pitches
with eaves (and record merges when one face touches several eaves).
Train the diffusion model to produce *that* graph given footprint +
those pitches. Now pitch-conditioning is learning the
**non-skeleton** styles in the dataset, which is the actual gap.
Whether those graphs remain a terrain at the *requested* pitches is
not guaranteed; that has to be checked by a geometry stage (next
section).

---

## 5. Can we modify Ren to condition on pitch?

**Yes, and they already named the geometry half of it.** The topology
half is the part they did not do, and it is only well-posed when
topology is still free after pitches are fixed.

### 5.1 Geometry stage: add a pitch energy (the natural modification)

Ren optimise vertex positions \(X\) for planarity, optionally
aesthetics, and a single height \(h\). Replace or supplement \(h\)
with a per-face pitch constraint.

Let face \(f\) have a target pitch \(\theta_f \in (0, 90]\) in the
sense of `CONTEXT.md` (angle between the face and the horizontal
plane). If \(\mathbf{n}_f\) is a unit normal of the current embedding
of \(f\), a differentiable residual is

\[
r_f = \bigl(\arcsin(|n_{f,z}|) - (90^\circ - \theta_f)\bigr)
\quad\text{or equivalently}\quad
\cos\theta_f - |\langle \mathbf{n}_f, \mathbf{e}_z \rangle|
\]

(choose the form that matches “pitch from horizontal” and stay in
degrees at the API, as ADR 0001 and `docs/future-work.md` already
insist — do not expose `cot(\theta)` to an optimiser).

Then, schematically:

\[
\min_{X_{\mathcal{R}}}
\;
E_{\text{planarity}}(X)
+ \lambda_{\theta} \sum_f r_f^2
+ \lambda_{\text{data}}\|\bar X_{\mathcal{R}} - \bar X^{\text{user}}_{\mathcal{R}}\|_F^2
\]

Gables: \(\theta = 90\) means “this eave has no face.” Drop that face
from \(F\) and from the sum; neighbouring faces meet the wall as
verges. That is the same discrete choice krovlab already has.

**What this does in the 1-face-per-eave class.** Each eave plus its
pitch defines a plane (the unique plane through that segment at that
inclination, rising inward). Interior vertices of a generic roof are
intersections of three such planes. That is the weighted straight
skeleton / classical roof model (Aichholzer et al.; Eppstein and
Erickson; the “blue planes from the outline” paragraph in Ren et al.
2021, §3.3). So:

- If the dual graph is the skeleton’s dual, pitch-constrained Ren
  should recover (a numerical approximation of) the same 3D roof as
  krovlab, when the WSS is unique.
- If the dual graph is *not* that dual, the planes may be
  over-constrained: no embedding is both planar-faced *and* at the
  requested pitches. The optimiser will bottom out at a non-zero
  residual. That is a feature: it is how you reject a topology.

**Aesthetic terms must be turned off or replaced** when pitches
differ. Equal-offset ridges and angle bisectors (Ren Eq. 3) contradict
weighted bisectors. Keeping them would pull the solution off the
architect’s pitches.

**Terrain / drainage.** Ren’s validity is planarity + non-zero height.
krovlab’s `validity` also requires: plan areas sum to the footprint,
sampled plan points have one height, water drains to each face’s own
eave, arc labels match geometry (`README.md`, `CONTEXT.md`). Pitch-
constrained Ren does not give those for free. After optimisation,
run the existing invariant checks and treat failure as a finite
penalty, not an exception (`docs/future-work.md`, Kelly and Wonka’s
failure mode on large sets).

### 5.2 Topology stage: condition the GCN on pitch (only sometimes)

Ren’s GCN maps an outline to \(p_{ij}\) (face \(i\) adjacent to face
\(j\)). To condition on pitch, concatenate \(\theta_i, \theta_j\) (and
gable flags) into the edge-pair features of their adjacency model
(their Fig. 18 / Appendix building blocks). That is a small change.

It is **worth doing** only if, given \((\text{footprint}, \boldsymbol{\theta})\),
several dual graphs are still plausible. That happens when we leave
the 1-face-per-eave class:

- Merged faces (one pitch on a plane that covers several walls) —
  the case [`limitations.md`](limitations.md) lists first.
- Extra or fewer interior vertices than the skeleton (Ren Fig. 2).
- Discrete style that pitches do not pin down (Ren Fig. 9), including
  which edges are gables if the architect did *not* specify them.
- Holes / courtyards, if encoded as a second cycle of dual nodes.

If we stay in 1-face-per-eave with fully specified pitches, the dual
is the WSS dual (when unique). Training a GCN to predict it is again
skeleton imitation.

### 5.3 Interactive editing already in Ren, automated

Their §6.4 operations — snap an edge, merge faces, split a face, force
adjacency — are exactly the moves that take a skeleton roof to a
roof the skeleton cannot emit. A network that predicts a *sequence of
edits* on top of krovlab’s output, then re-solves with the pitch
energy of §5.1, is a hybrid that:

- starts from a valid terrain at the requested pitches,
- only proposes topologies that still lift at those pitches,
- has a clear failure mode (residual or `validity.is_terrain == false`).

That is closer to a design assistant than either RoofDiT or Ren’s
from-scratch GCN.

---

## 6. A pipeline that matches the architect’s inputs

Do not pick “RoofDiT or Ren” as a wholesale replacement for krovlab.
Compose them so pitch stays a hard input.

```
Architect
  footprint P, pitches θ (per eave or per requested face),
  optional gable mask, optional overhang
        |
        v
[1] Weighted straight skeleton (krovlab)
        |  always available, unique in the generic 1-face-per-eave class
        v
[2] Topology proposer  (optional; this is the research object)
        |  inputs: P, θ, skeleton graph G_ss
        |  outputs: one or more dual/primal graphs G
        |  mechanisms, in order of how well they fit:
        |    (a) enumerate gable masks and merged-face candidates
        |    (b) GCN on eaves, pitch-conditioned (Ren §5, modified)
        |    (c) edit sequence on G_ss (Ren §6.4 ops, learned)
        |    (d) diffusion on interior vertices (RoofDiT, pitch tokens)
        |
        v
[3] Geometry solver
        |  pitch-constrained planarity (Ren §4 + §5.1 of this note)
        |  or plane intersection when 1-face-per-eave (WSS itself)
        |
        v
[4] krovlab validity  (terrain, drainage, labels, areas)
        |
        v
    admissible roofs, ranked by takeoff / attic / user style
```

**Step [2] is idle** when the architect wants “the” hipped or mixed
hip-and-gable roof at these pitches. That is today’s `roof()`.

**Step [2] earns its keep** when they want a roof in class (3) of
§2: wrapping a corner without a hip, dropping skeleton artefacts,
another ridge layout on the same plan.

RoofDiT, unmodified, is a candidate for [2d] that forgets \(\theta\)
and stops at 2D. Ren unmodified is [2b] + [3] without \(\theta\).
Point2WSS is [3] with \(\theta\) *predicted* from LiDAR, not typed.

---

## 7. What would actually be novel (and what would not)

Reviewers at TOG, ISPRS, CAGD, or a computational-geometry venue will
know Ren 2021, RoofDiT 2026, Loops2Roofs 2026, and the RTG papers.
“We used a GNN” is not a contribution. Pitch as a *design* condition
on a graph that is *not* forced to be a skeleton is still thinly
covered: Ren named slope constraints and did not implement them;
RoofDiT and Loops2Roofs do not take pitch; Point2WSS takes slope but
keeps the skeleton.

| Claim | Verdict |
|---|---|
| GNN predicts interior nodes from the outline | Already Ren’s primal/dual + GCN, and RoofDiT’s node diffusion. |
| Diffusion on 2D roof graphs given a footprint | RoofDiT. |
| 3D loops given a footprint | Loops2Roofs. |
| Predict pitches, then WSS | Point2WSS. |
| **Specified pitches + graph topology outside WSS, with a terrain certificate** | Not in the papers above. |
| **Pitch-constrained Ren optimiser** | Named in Ren §7, not done. Engineering + evaluation could be a paper if the topologies are strictly larger than WSS and validity is measured as krovlab measures it. |
| Characterise which graphs on a given cycle admit a terrain lift at given pitches | Theory; closer to SoCG / CGTA. `docs/future-work.md` already notes that enumerating topology cells of weighted skeletons is unpublished. |

A paper that trains RoofDiT on krovlab labels to reproduce the
skeleton should not be written.

---

## 8. First experiments (before any network)

These are cheap and they decide whether [2] is worth building.

1. **Lift Ren’s dataset at measured pitches.** For each of the 2539
   meshes, compute per-face pitch from the plane. Re-solve their
   optimiser *with* the pitch energy of §5.1, starting from their
   graph. How often does `validity.is_terrain` pass? If it rarely
   does, their graphs are not construction-valid at those pitches
   (they were fitted to images, not to drainage).
2. **Same footprints through krovlab.** Compare skeleton graphs to
   Ren’s graphs: extra vertices, merged faces, different duals. That
   is the empirical size of the gap [`limitations.md`](limitations.md)
   describes.
3. **Pitch ablation on a fixed Ren dual.** Hold the dual graph of
   Fig. 10-style examples, vary \(\boldsymbol{\theta}\), run §5.1. Confirm
   that unequal pitches move the ridge off the median (they must) and
   that aesthetic terms, if left on, fight the pitch residual.
4. **Infeasible topologies.** Deliberately merge faces that cannot
   share a plane at the requested pitches. Confirm the residual does
   not go to zero. That residual is the training signal for a
   proposer that must not emit them.

Only if (1)–(2) show a set of *buildable* non-skeleton roofs at
stated pitches is a GCN or a diffusion model worth training.

---

## 9. Recommended reading order

1. This project: [`CONTEXT.md`](../CONTEXT.md),
   [`limitations.md`](limitations.md),
   [ADR 0001](adr/0001-own-weighted-straight-skeleton-in-python.md).
2. Ren et al. 2021, §§3–5 and §7 (slope as future work). Code is
   public.
3. Held and Palfrader 2017 — additive weights; what a graph model
   still has to express if we ever want half-hips.
4. Biedl et al. 2015 — why weighted skeletons are combinatorially
   fragile.
5. Panangian and Bittner 2026 (RoofDiT) — footprint-conditioned 2D
   graphs vs skeleton, with numbers; explicit “no 3D / no heights.”
6. Queffélec et al. 2026 (Point2WSS) — the parametric model that
   *does* use per-edge slope, still inside WSS.
7. Xiong, Oude Elberink, Vosselman 2014 — dual RTG vocabulary and
   typical combinatorial errors.
8. Guo et al. 2026 (Loops2Roofs) — the other current generative 3D
   representation; still not pitch-conditioned.

---

## 10. Sources

Only works cited above. URLs are the copies used while writing this
note.

Aichholzer, O., Aurenhammer, F., Alberts, D., and Gärtner, B. (1995).
A novel type of skeleton for polygons. *Journal of Universal Computer
Science* 1(12):752–761.

Aichholzer, O. and Aurenhammer, F. (1996). Straight skeletons for
general polygonal figures in the plane. In *Computing and Combinatorics
(COCOON)*, Springer, 117–126.
[doi:10.1007/3-540-61332-3_144](https://doi.org/10.1007/3-540-61332-3_144)

Amrullah, C., Panangian, D., and Bittner, K. (2025). PolyRoof: precision
roof polygonization in urban residential building with graph neural
networks. In *JURSE 2025*, 1–4.

Bauchet, J.-P. and Lafarge, F. (2020). Kinetic shape reconstruction.
*ACM Transactions on Graphics* 39(5).
[doi:10.1145/3376918](https://doi.org/10.1145/3376918)

Biedl, T., Held, M., Huber, S., Kaaser, D., and Palfrader, P. (2015).
Weighted straight skeletons in the plane. *Computational Geometry*
48(2):120–133.
[doi:10.1016/j.comgeo.2014.08.006](https://doi.org/10.1016/j.comgeo.2014.08.006)

Buron, C., Marvie, J.-E., and Gautron, P. (2013). GPU Roof Grammars.
In *Eurographics 2013 — Short Papers*.

Eppstein, D. and Erickson, J. (1999). Raising roofs, crashing cycles,
and playing pool: applications of a data structure for finding pairwise
interactions. *Discrete & Computational Geometry* 22(4):569–592.
(Conference version: SCG 1998.)
[doi:10.1007/PL00009476](https://doi.org/10.1007/PL00009476)

Felkel, P. and Obdržálek, Š. (1998). Straight skeleton implementation.
In *Proceedings of Spring Conference on Computer Graphics*.

Guo, J., Li, P., Zeng, Q., Zhang, W., Li, P., Nan, L., Beneš, B., and
Yan, D.-M. (2026). Loops2Roofs: diffusion-based 3D roof generation using
a loop representation. *ACM Transactions on Graphics*.
[doi:10.1145/3807955](https://doi.org/10.1145/3807955)

Held, M. and Palfrader, P. (2017). Straight skeletons with additive and
multiplicative weights and their application to the algorithmic
generation of roofs and terrains. *Computer-Aided Design* 92:33–41.
[doi:10.1016/j.cad.2017.07.003](https://doi.org/10.1016/j.cad.2017.07.003)

Huber, S. and Held, M. (2012). A fast straight-skeleton algorithm based
on generalized motorcycle graphs. *International Journal of
Computational Geometry & Applications* 22(5):471–498.
[doi:10.1142/S0218195912500124](https://doi.org/10.1142/s0218195912500124)

Hu, S., Wu, W., Wang, Y., Xu, B., and Zheng, L. (2024). GSDiff:
synthesizing vector floorplans via geometry-enhanced structural graph
generation. arXiv:2408.16258.

Kelly, T. and Wonka, P. (2011). Interactive architectural modeling with
procedural extrusions. *ACM Transactions on Graphics* 30(2).
[doi:10.1145/1944846.1944854](https://doi.org/10.1145/1944846.1944854)

Kipf, T. N. and Welling, M. (2017). Semi-supervised classification with
graph convolutional networks. *ICLR 2017*. (Ren et al. cite the 2016
arXiv version.)

Müller, P., Wonka, P., Haegler, S., Ulmer, A., and Van Gool, L. (2006).
Procedural modeling of buildings. *ACM Transactions on Graphics*
25(3):614–623.
[doi:10.1145/1141911.1141931](https://doi.org/10.1145/1141911.1141931)

Nan, L. and Wonka, P. (2017). PolyFit: polygonal surface reconstruction
from point clouds. In *ICCV 2017*, 2353–2361.
[doi:10.1109/ICCV.2017.258](https://doi.org/10.1109/ICCV.2017.258)

Panangian, D. and Bittner, K. (2026). Diffusion transformers for roof
graph synthesis and reconstruction. arXiv:2608.25652.
<https://arxiv.org/abs/2608.25652>

Qian, Y., Zhang, H., and Furukawa, Y. (2021). Roof-GAN: learning to
generate roof geometry and relations for residential houses. In
*Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern
Recognition (CVPR)*, 2796–2805.
[doi:10.1109/CVPR46437.2021.00282](https://doi.org/10.1109/CVPR46437.2021.00282)
[arXiv:2012.09340](https://arxiv.org/abs/2012.09340)

Queffélec, P.-L., Trouvé, N., Roussel, S., Wu, T., and Vallet, B.
(2026). Point2WSS: reconstructing LoD2 buildings from aerial LiDAR data
using multimodal learning and weighted straight skeleton. *ISPRS Annals
of the Photogrammetry, Remote Sensing and Spatial Information Sciences*
XI-2-2026:331–340.
[doi:10.5194/isprs-annals-XI-2-2026-331-2026](https://doi.org/10.5194/isprs-annals-XI-2-2026-331-2026)

Ren, J., Zhang, B., Wu, B., Huang, J., Fan, L., Ovsjanikov, M., and
Wonka, P. (2021). Intuitive and efficient roof modeling for
reconstruction and synthesis. *ACM Transactions on Graphics* 40(6).
[doi:10.1145/3478513.3480494](https://doi.org/10.1145/3478513.3480494)
[arXiv:2109.07683](https://arxiv.org/abs/2109.07683)
Code: <https://github.com/llorz/SGA21_roofOptimization>

Xiong, B., Oude Elberink, S., and Vosselman, G. (2014). A graph edit
dictionary for correcting errors in roof topology graphs reconstructed
from point clouds. *ISPRS Journal of Photogrammetry and Remote Sensing*
93:227–242.
[doi:10.1016/j.isprsjprs.2014.04.005](https://doi.org/10.1016/j.isprsjprs.2014.04.005)

Zhao, W., Persello, C., and Stein, A. (2022). Extracting planar roof
structures from very high resolution images using graph neural networks.
*ISPRS Journal of Photogrammetry and Remote Sensing* 187:34–45.
[doi:10.1016/j.isprsjprs.2022.02.022](https://doi.org/10.1016/j.isprsjprs.2022.02.022)

Zorzi, S., Bazrafkan, S., Habenschuss, S., and Fraundorfer, F. (2022).
PolyWorld: polygonal building extraction with graph neural networks in
satellite images. In *CVPR 2022*, 1848–1857.
