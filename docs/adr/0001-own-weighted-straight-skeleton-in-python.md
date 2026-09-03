# 1. Own weighted straight skeleton, in Python

Date: 2026-09-03

## Status

Accepted. Reverses the TypeScript + CGAL-to-WebAssembly direction taken during
the second grilling round, which was never implemented.

## Context

The core of this project is generating a roof from a footprint using a weighted
straight skeleton. Where that algorithm comes from decides almost everything
else, so it was settled first.

Three constraints were live at the time of the earlier decision, and two of them
have since gone away:

1. *The app must run with no server, ever.* Now relaxed — a hosted demo may cost
   money.
2. *The optimizer needs thousands of geometry evaluations, so it must run
   in-process.* Now deferred — optimization is parked as future work.
3. *We must be able to improve the core if necessary.* New, and it points the
   opposite way from the earlier decision.

Those first two were the entire justification for compiling CGAL to WebAssembly
ourselves, which was also the single riskiest task in the plan. With them gone,
the risk buys nothing.

What the alternatives actually offer:

**CGAL** genuinely solves this problem. Since 5.6 it has weighted straight
skeletons and an `extrude_skeleton()` that takes per-edge angles and returns a
2-manifold roof mesh for polygons with holes. But it is C++, and reaching it
from Python is worse than it looks: `scikit-geometry` is not on PyPI at all
(conda only), and the other bindings do not expose the weighted entry points.
Reaching it means writing and shipping a pybind11 wrapper — comparable work to
the WebAssembly build we are trying to avoid, with the same toolchain fragility.

CGAL also fixes our ceiling at what CGAL supports: positive multiplicative
weights, no additive weights, therefore no half-hips or knee-walls ever. And
`Straight_skeleton_2` is GPL, which would make the whole project GPL.

**Existing pure-Python ports** (`polyskel`, `bpypolyskel`) are unweighted, not
on PyPI, and `bpypolyskel`'s own README says it "does not provide a straight
skeleton in a mathematical sense."

**Writing it ourselves** is the option the literature warns about. Weighted
straight skeletons are ambiguous at parallel adjacent edges of differing weight,
and Biedl et al. showed weighted skeletons of simple polygons may contain cycles
and crossings. Robustness is the hard part, and degenerate inputs are where
implementations break.

## Decision

Implement the weighted straight skeleton ourselves, in Python, as the core
library. No CGAL, no WebAssembly, no native build step.

Confine ourselves to strictly positive multiplicative weights, which is the
regime where Biedl et al. show weighted skeletons behave essentially like
unweighted ones. Pitch strictly between 0° and 90° gives this for free.
`weight = 0` is admitted only as the explicit vertical-face (gable) case.

Use the Felkel–Obdržálek wavefront formulation: a priority queue of events over
a circular list of active vertices. Not the sub-quadratic motorcycle-graph
algorithms — at the polygon sizes an architect draws, the constant factors and
the implementation risk dominate the asymptotics.

## Consequences

We own the robustness problem. This is the real cost, and it is why the first
milestone is correctness on a corpus of real footprints rather than features.

In exchange we can instrument the algorithm freely — hash the combinatorial
structure to detect topology changes, expose the wavefront at intermediate
times for debugging, make tie-breaking deterministic. Every one of those is
needed later by the optimizer and none is reachable through a library boundary.
Additive weights, and therefore half-hips, stay possible instead of being
permanently foreclosed.

The project can be permissively licensed rather than GPL, since no CGAL code is
linked.

The web app now needs a server, or a build step that gets Python into the
browser. That is deliberately unresolved; see the note in `docs/future-work.md`.
Nothing in the core library may assume either answer: it takes data and returns
data.

Being slower than CGAL is acceptable. A single roof is interactive either way,
and the case that would have cared — an optimizer doing thousands of
evaluations — is not being built yet.

If robustness defeats us, the exit is to wrap CGAL after all. Keeping the core
a pure data-in/data-out module is what keeps that exit cheap, so it is a
constraint on the design, not just a hope.
