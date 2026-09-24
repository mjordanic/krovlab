# 03: Let the checkpoint choose the face graph

**What to build:** The visitor picks the experimental method, picks or draws one footprint, and submits. The page loads the shipped checkpoint, predicts which faces share a boundary, and lifts that graph. It does not train, and it does not ask for a face graph.

The explanation now says a network chooses which faces meet, a planarity step makes those faces planar, and pitch is not an input. It says to use this method for a face over several walls or for another ridge layout, and to keep the skeleton when each wall has a pitch.

A catalog example roofs under either method. At least one footprint the skeleton already roofs comes back with a different arrangement of which faces meet. The comparison is that arrangement, not the coordinates. A predicted graph that cannot be lifted is Failure `unliftable`. A supplied face graph, as in the previous ticket, still roofs without the checkpoint.

`import krovlab` still pulls in no third-party package. PyTorch loads only when the experimental path runs.

**Blocked by:** 01: Train and ship the face-adjacency checkpoint. 02: Choose the method, and roof one footprint from a face graph.

**Status:** done

**Stories:** 6, 7, 14, 16, 20, 21

**Prior art:** The experimental entry point and Failure kinds `unliftable` and `no_face_graph` from ticket 02. The form POST tests. The checkpoint and the recorded held-out score from ticket 01. PRD: the page loads the checkpoint and does not train; slope constraints stay out.

**Artifact homes:** None new. Reads `models/ren2021-face-adjacency.pt` from ticket 01.

- [x] Submitting a footprint on the experimental path, with no supplied face graph, roofs it from the committed checkpoint
- [x] That request does not train and does not fetch the published pairs
- [x] The explanation names the network, the planarity step, that pitch is not used, and when to prefer this method over the skeleton
- [x] A catalog example produces a roof under the skeleton and a roof under the experimental method
- [x] At least one footprint comes back with a different face arrangement from the skeleton on the same walls
- [x] A predicted graph that cannot be lifted is Failure `unliftable`
- [x] Passing a face graph still returns that graph's roof without consulting the checkpoint
- [x] `import krovlab` still imports no third-party package
