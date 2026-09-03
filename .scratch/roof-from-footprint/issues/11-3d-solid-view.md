# 11: Interactive 3D view of the roof solid

**What to build:** The architect looks at his roof in 3D and orbits it, judging
whether it looks right — which is a judgement no invariant can make for him. He
saves that view as a single HTML file that opens from his desktop and can be
sent to a client.

The view is of the roof solid, built from the faces and node heights the roof
already carries. There is no lifting step to write: a node's height is the time
at which it was created, and the roof already reports it.

Like the plan view, this consumes a roof and returns a figure, lives in the
optional visualisation module, and never reaches past the entry point.

**Blocked by:** 05

**Status:** ready-for-agent

**Prior art:** Ticket 05 established the visualisation module, its Plotly
figure-returning shape, its self-contained HTML export and its smoke-test bar —
follow all four rather than inventing a second pattern. The feature PRD's
"Visualisation uses Plotly and is a separate, optional module" decision explains
why Plotly rather than a 3D engine, and "The third dimension is not a separate
step" explains why the heights are simply there. Every glossary arc type from
`CONTEXT.md` should stay legible in 3D.

- [ ] A roof renders as an orbitable 3D solid
- [ ] The solid's face heights match the node heights the roof reports
- [ ] The view saves as one self-contained HTML file that opens over `file://`
      with no server
- [ ] Roofs from every supported footprint class render: convex, reflex, holed,
      gabled, overhung, per-edge pitch
- [ ] The core package still imports nothing third-party
- [ ] Smoke tests assert the figure builds; nothing asserts on pixels
