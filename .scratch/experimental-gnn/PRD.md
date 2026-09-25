# PRD: Experimental roof from a face-adjacency network

Status: ready-for-agent

Vocabulary in this document is defined in `CONTEXT.md`. Terms are used in their
glossary sense — footprint, wall, pitch, roof, face, plan area, sloped area,
ridge, hip, valley, eave, verge, overhang, eave height, terrain, takeoff,
Failure — and not loosely. Do not call the footprint an outline. Respects
ADR-0001 (the weighted straight skeleton stays the core, in Python, with no
third-party dependencies) and ADR-0002 (the Python form server wraps the core).
This method does not replace that skeleton.

## Problem Statement

The skeleton returns one roof for a footprint and a pitch per wall. Two
buildable roofs on the same walls are missing. A face that covers several
non-collinear walls cannot occur. A different arrangement of ridges on the
same footprint is not generated. Both limits are already written down.

Ren, Zhang, Wu, Huang, Fan, Ovsjanikov, and Wonka (SIGGRAPH Asia 2021,
"Intuitive and Efficient Roof Modeling for Reconstruction and Synthesis")
publish a different method. A graph network predicts which faces share a
boundary. A planarity optimisation then lifts that graph into a roof. It
can represent a face over several walls, and more than one ridge layout
on the same footprint. It does not take pitch.

Their repository publishes the training pairs and does not publish the
network weights or the network source. The source is specified in the
supplement. Training it is required. The visitor should not have to train
it to try the method.

There is no way, on the page or in a notebook, to ask for this method
instead of the skeleton, or to read when one is the better choice.

## Solution

A second way to roof one footprint, beside the skeleton. The visitor
chooses it at the very top of the page. The skeleton stays the default,
and every control that exists today keeps today's meaning on that path.

The experimental path trains the published face-adjacency network, ships
the checkpoint, and roofs a footprint by predicting which faces meet and
then lifting that graph so the faces are planar. The page says, in a few
sentences, how that works and when to use it instead of the skeleton.
A notebook walks the same examples. The README describes it in the same
voice as the sections already there.

Pitch is not an input. Knee height, gambrel, gable, holes, dormers, and
a project of several cells are not this method. Overhang and eave height
still apply: overhang offsets the footprint first, eave height lifts the
finished roof, the same meanings they have on the skeleton.

## User Stories

1. As a visitor, I want the skeleton selected when I open the page, so that the tool I already use does not change until I opt in.
2. As a visitor, I want the choice at the very top of the page, above the example catalog, so that I see the two methods before any other control.
3. As a visitor, I want the two choices labelled as the standard skeleton and as an experimental graph network, so that I know which one is the settled method.
4. As a visitor who leaves the skeleton selected, I want pitch, gable, knee, gambrel, overhang, eave height, a hole, several cells, and a dormer to behave exactly as they do today.
5. As a visitor who leaves the skeleton selected, I want the same plan, the same 3D solid, and the same Failure as today for the same inputs.
6. As a visitor who switches to the experimental method, I want a short explanation of the method, so that I know a network chooses which faces meet and a planarity step then makes those faces planar.
7. As a visitor who switches to the experimental method, I want to read when it is the better choice, so that I use it for a face over several walls or for another ridge layout, and I keep the skeleton when the pitch of each wall is the point.
8. As a visitor who switches to the experimental method, I want the page to say that pitch is not an input, so that I do not think the pitch I typed was used.
9. As a visitor who switches to the experimental method, I want gable, knee, gambrel, holes, dormers, and extra cells to be visibly not part of this method, so that I am not shown a skeleton roof under an experimental label.
10. As a visitor who switches to the experimental method on a single footprint, I want a roof, so that I can compare it with the skeleton on the same walls.
11. As a visitor, I want the plan and the 3D solid of that roof, so that I can see the faces and the ridges rather than only a probability.
12. As a visitor, I want `validity.is_terrain` on that roof, so that I know whether the takeoff is usable, the same rule as any other roof.
13. As a visitor, I want sloped area, plan area, and the lengths of eaves, hips, valleys, ridges, and verges when the roof is a terrain, so that the takeoff still means what the rest of the tool means.
14. As a visitor, I want a named Failure when the predicted graph cannot be lifted into a roof, so that I am not shown a broken solid.
15. As a visitor, I want a face that covers several non-collinear walls when the predicted graph says those walls are one face, so that I can see a roof the skeleton cannot represent.
16. As a visitor, I want a ridge layout that is not the skeleton's layout when the predicted graph says so, so that I can see the other style the skeleton will not emit.
17. As a visitor, I want overhang to enlarge the footprint before the experimental method runs, so that the eaves still sit past the walls by the distance I set.
18. As a visitor, I want eave height to lift the experimental roof, so that ridge height is still measured above datum.
19. As a visitor, I want switching back to the skeleton and submitting to restore the skeleton roof, so that the choice is the thing that changed.
20. As a visitor, I want an example from the catalog to roof under either method, so that I can compare them without drawing a footprint.
21. As a visitor, I want the experimental choice not to start a training run, so that the page answers in the time of a roof, not the time of a fit.
22. As a reader of the README, I want a section in the same voice as the sections already there, so that I learn what the method takes, what it returns, when to prefer it, and how to train it.
23. As a reader of the README, I want the license of the training pairs named, so that I know the fit depends on a CC BY-NC 4.0 dataset I do not own.
24. As a reader of the notebook, I want the same footprint roofed both ways, so that I can see the difference in quantities and in the drawing.
25. As a reader of the notebook, I want one example where the experimental roof puts one plane over several walls, so that I see the case the skeleton refuses.
26. As a reader of the notebook, I want one example where the pitches differ per wall and the text says to keep the skeleton, so that the notebook teaches the same choice as the page.
27. As a reader of the notebook, I want a named Failure example, so that I see what an unliftable graph looks like.
28. As someone reproducing the fit, I want one command that fetches the published pairs and trains the network from the supplement, so that the checkpoint is not a blob nobody can rebuild.
29. As someone reproducing the fit, I want the downloaded pairs kept out of git, so that the CC BY-NC dataset is not vendored into this repo.
30. As someone reproducing the fit, I want the checkpoint committed, so that the page and the notebook run without the dataset and without a GPU.
31. As someone reproducing the fit, I want the held-out intersection-over-union written down next to the checkpoint, so that a later fit can be compared with this one and with the paper's reported figure.
32. As a maintainer, I want `import krovlab` to keep working with no third-party packages, so that the skeleton core stays what ADR-0001 says it is.
33. As a maintainer, I want the experimental entry point to return a Roof or a Failure, so that the existing plan and 3D views draw it without a second viewer.
34. As a maintainer, I want an ADR that the skeleton remains the default and this method is optional and unpitched, so that a later reader does not "fold the network into `roof`" and pull PyTorch into the core.

## Implementation Decisions

- The skeleton is unchanged. `roof` and `project` keep their arguments and their results. The experimental method is a second entry point. It takes one footprint, an optional overhang, an optional eave height, and an optional face graph (which walls share a face, including one face over several walls). It returns a Roof or a Failure. It does not take a pitch. The page never asks the visitor to draw the face graph. When the graph is omitted, the shipped checkpoint predicts it. A call with neither a supplied graph nor a checkpoint is Failure `no_face_graph`. A graph that cannot be lifted is Failure `unliftable`.
- The page offers the choice at the top, above the catalog. Default is the skeleton. Choosing the experimental method and submitting calls the second entry point. Choosing the skeleton calls `roof` / `project` as today.
- On the experimental path the page shows a short explanation: the network predicts which faces share a boundary; a planarity optimisation lifts that graph into a roof; pitch is not an input. The same text says to use it when the wanted roof is a face over several walls or another ridge layout, and to use the skeleton when each wall has a pitch.
- Gable, knee, gambrel, holes, dormers, and further cells are not inputs of the experimental entry point. The page makes that visible on that path. It does not silently roof them with the skeleton.
- Overhang is applied by offsetting the footprint first, the same meaning as on the skeleton. Eave height is added to every node after the roof exists, the same meaning as on the skeleton.
- A Roof from this method is run through the same terrain check as any other Roof. Quantities use the same definitions. A graph that cannot be lifted is a named Failure, not a Roof.
- A face from this method may cover several walls. That is the point of the method, and it is outside the glossary sentence that a face rises from one footprint edge. The glossary gains one sentence: that sentence is the skeleton's rule; an experimental face may span several walls. The glossary stays a glossary.
- An ADR records the trade-off: the skeleton remains the default and the only core; this method is optional, does not take pitch, and depends on PyTorch. The core does not import PyTorch.
- The network is the face-adjacency model in appendix B.2 of Ren et al. 2021, not the outline transformer in the same paper. Four blocks, with the published widths. Each block updates an adjacency feature, an edge feature, and a global feature, except the last block, which updates adjacency only. A linear layer turns the last adjacency feature into a logit. The loss is binary cross-entropy against the labelled pairs. The initial edge feature is the midpoint, the inward unit normal, and the length. Vertices are centred and scaled isotropically into [-1, 1] before that. Training augments with a random rotation and a scale in [0.8, 1.2].
- The supplement says the initial adjacency feature and the initial global feature are zeros, and does not state their width. They are width 0: the first block has nothing extra to concatenate. Later blocks concatenate the features the previous block produced.
- The two MLPs inside a block are a linear layer, a ReLU, and a linear layer. The paper cites Battaglia et al. 2018 for the block and does not name the activation. A linear stack with no activation would not be a network.
- The published pairs are the `.outline` / `.adjacency` files in the RoofSynthesis raw data of `llorz/SGA21_roofOptimization` (2539 roofs). The files are cloned when training runs. They are gitignored. They are not copied into this repo.
- The published train/test membership was not released. The split keeps their counts: sorted by name, 239 held out, then 4-vertex footprints dropped from both sides, as appendix B.1 describes. The held-out intersection-over-union is therefore not the paper's 97.30% on their unreleased split. The number this split reaches is recorded with the checkpoint. The paper's figure is the neighbourhood to aim at, not a number to fake.
- Learning rate, batch size, and epoch count are not in the supplement for this network. They are chosen so the held-out score is in that neighbourhood, and the values that produced the shipped checkpoint are recorded with it in `models/ren2021-face-adjacency.md`.
- The page and the notebook load the shipped checkpoint. They do not train.
- The planarity lift is Ren et al.'s planarity metric (their section 4), reimplemented here. Their code for that step is MATLAB and is not called. One roof height is fixed so the flat roof is not the minimiser, as in their formulation. Pitch is not added. Slope constraints are future work in their section 7 and are out of scope here.
- The checkpoint is committed on a path git does not ignore. The README section and the notebook are committed. The notebook lives at `notebooks/experimental-gnn.ipynb`. The checkpoint lives at `models/ren2021-face-adjacency.pt`, with the held-out score and the hyperparameters in `models/ren2021-face-adjacency.md`. The downloaded pairs live under `data/ren2021/`, which is gitignored. None of `notebooks/experimental-gnn.ipynb`, `models/ren2021-face-adjacency.pt`, `models/ren2021-face-adjacency.md`, or `README.md` is ignored.

## Testing Decisions

A good test calls the experimental entry point, or the form, and asserts what comes back. It does not assert layer activations, optimiser iterations, or the text of a log line.

The one algorithmic seam is that entry point: a footprint in, a Roof or a Failure out. That is the same shape as `roof`, which is the seam the single-footprint tests already use. Prefer it to a test that reaches into the network. The form is the existing form-server seam: it only decides which entry point runs, and it shows the explanation.

Test the entry point the way the single-footprint tests test `roof`:

- A Roof carries validity, and a terrain roof's plan areas and arc kinds use the same definitions as any other Roof.
- A footprint whose labelled graph covers several walls with one face comes back with that face, not with one face per wall.
- A footprint the skeleton already roofs can come back with a different ridge layout. The test compares the two roofs by which faces meet, not by coordinates alone.
- Pitch is not an argument. Overhang and eave height change the roof in the same way they do for the skeleton: eaves outside the walls, heights shifted by the eave height.
- An unliftable graph is Failure `unliftable`. A call with neither a supplied face graph nor a checkpoint is Failure `no_face_graph`.

Test the form the way the form-server tests already test a POST:

- The first response has the skeleton selected, and a skeleton result matches today's page.
- The experimental choice shows the short explanation, including that pitch is not used and when to prefer which method.
- A POST with the experimental choice roofs through the experimental entry point. A POST with the skeleton still roofs through `roof`.

The training command is not a unit test of the full dataset. A small test checks that the network's external behaviour is right: symmetric probabilities for a pair of edges, and a single synthetic labelled footprint that the network can memorise. The full fit is checked by the recorded held-out score.

Prior art: the tests that call `roof` and branch on Roof versus Failure, including overhang and eave height; the tests that POST the form and read the returned page.

## Out of Scope

- The outline transformer from the same paper. It invents new footprints. It does not roof a footprint the visitor already has.
- Putting pitch, slope constraints, or per-wall weights into the network or the planarity lift. Ren et al. name that as future work and do not do it.
- Training a network to imitate the skeleton.
- Knee height, gambrel, gable ends, holes, dormers, and a project of several cells on the experimental path.
- Changing the skeleton, its weights, or its failures.
- The help agent. It keeps filling the skeleton's knobs. It does not gain a method switch.
- Vendoring the published images, meshes, or adjacency pairs.
- Calling their MATLAB optimiser.
- A commercial license review beyond naming CC BY-NC 4.0 on the pairs and on the checkpoint trained from them.

## Further Notes

The checkpoint is a derivative of a CC BY-NC 4.0 dataset. Shipping it is what makes the page run without training. The README has to say that, and that commercial use of those pairs or of the checkpoint needs the authors' permission.

Their RoofSynthesis code loads `checkpoint.pth.6` for the outline transformer. That file is not in the repository (HTTP 404). There is no graph-network source file and no graph-network weight file in the tree. The decision to train is because of that absence, not instead of a file we failed to download.

`CONTEXT.md` currently says a face rises from one footprint edge. That remains true for the skeleton. The experimental method exists to break it. The glossary sentence added above is the whole vocabulary change. Do not turn `CONTEXT.md` into a second copy of this PRD.
