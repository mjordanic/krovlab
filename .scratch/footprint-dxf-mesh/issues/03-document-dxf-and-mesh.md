# 03: Document the DXF and the mesh

**What to build:** A reader can try the demo from the README and from the
getting-started notebook, using the same 10 × 6 m rectangle the rest of the
docs already roof.

Commit an ASCII DXF, `notebooks/hip-rectangle-mm.dxf`: one closed straight
polyline in model space, vertices `(0,0)`, `(10000,0)`, `(10000,6000)`,
`(0,6000)` in millimetres. The README Web demo section explains the upload,
the unit choice, what a file must contain, the ignored junk, the explode hint,
**Update roof**, and the two downloads, and links that file. The Notebooks
list mentions the new walkthrough. No core function, and no example under the
Python Examples heading.

The getting-started notebook gains one markdown section, in the same voice as
the existing web-demo callouts, and the opening list of topics includes it.
The section points at that file and at the rectangle the notebook already
roofs. No code cell imports the web stack or the DXF reader.

One HTTP test uploads that committed file with millimetres, then **Update
roof** at set-pitch 45°, and both downloads are the solid whose ridge runs
from `(3, 3, 3)` to `(7, 3, 3)`.

**Blocked by:** 01-upload-dxf-footprint, 02-download-roof-mesh

**Status:** ready-for-agent

**Stories:** 40, 41, 42, 43, 44, 45

**Prior art:** README "Web demo" and "Notebooks" sections. Getting-started
notebook web-demo callouts (concatenated gables, knee, gambrel, dormer) and
its opening topic list. PRD "Worked file" and "Docs, same homes as the other
capabilities". Worked numbers: 10 × 6 m at 45°, ridge from `(3, 3, 3)` to
`(7, 3, 3)`. Ticket 01's upload behaviour and ticket 02's OBJ / glTF
coordinates. Artifact homes: `README.md`, `notebooks/getting-started.ipynb`,
`notebooks/hip-rectangle-mm.dxf`. None of these paths is gitignored.

- [ ] `notebooks/hip-rectangle-mm.dxf` is the millimetre 10 × 6 m rectangle, one closed straight polyline in model space
- [ ] README Web demo explains upload, units, what is ignored, the explode hint, **Update roof**, and both downloads, and links that file
- [ ] README Notebooks list mentions the walkthrough; the Python Examples heading grows no file-format example
- [ ] Getting-started gains one markdown section and lists it up front; the notebook still runs without the web extra
- [ ] Uploading that file at millimetres, then **Update roof** at 45°, offers both downloads of the ridge from `(3, 3, 3)` to `(7, 3, 3)`
