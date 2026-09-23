# 04: README and notebook

**What to build:** The README gains a section in the same voice as the sections already there. It says what the experimental entry point takes (a footprint, optional overhang, optional eave height; not a pitch), what it returns (a Roof or a Failure), and when to use it: a face over several walls, or another ridge layout. It says to keep the skeleton when each wall has a pitch. It names the training command, states that the pairs and the checkpoint are CC BY-NC 4.0, and states that commercial use needs the authors' permission. It points at the held-out score recorded beside the checkpoint.

The notebook walks four examples. The same footprint is roofed both ways. One experimental roof puts one plane over several non-collinear walls. One note says to keep the skeleton when the pitches differ per wall. One call is Failure `unliftable` or Failure `no_face_graph`, and the notebook shows the kind and the reason.

**Blocked by:** 03: Let the checkpoint choose the face graph

**Status:** ready-for-agent

**Stories:** 22, 23, 24, 25, 26, 27

**Prior art:** The README "Examples" and "Web demo" sections for voice. The getting-started notebook for how a worked roof is shown. The experimental entry point, the checkpoint, and Failure `unliftable` from tickets 02 and 03. `models/ren2021-face-adjacency.md` for the score the README cites.

**Artifact homes:** README section in `README.md` (tracked). Notebook at `notebooks/experimental-gnn.ipynb` (tracked; `notebooks/` is not ignored).

- [ ] The README section matches the voice of the existing sections and covers inputs, the Roof-or-Failure return, when to prefer which method, the training command, and CC BY-NC 4.0 including commercial use
- [ ] The README cites the held-out score in `models/ren2021-face-adjacency.md`
- [ ] The notebook roofs one footprint with the skeleton and with the experimental method
- [ ] The notebook shows an experimental face that covers several non-collinear walls
- [ ] The notebook says to keep the skeleton when pitches differ per wall
- [ ] The notebook shows a named Failure with its kind and reason
