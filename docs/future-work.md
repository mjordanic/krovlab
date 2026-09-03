# Future work

Deliberately deferred. Nothing here is being built now; the current milestone is
a weighted straight skeleton that is correct on real footprints.

This file exists so the research behind these decisions isn't re-done. Each
section records what we found, what we concluded, and what would have to be
true to start.

---

## 1. Cost optimization

### Why it's parked

Because the obvious version of it is a trick question. Every dominant cost
driver grows monotonically with pitch — sloped area as `1/cos θ`, hip and valley
lengths as the rake length, labour via steep-roof surcharges, cut waste on
hip-rich geometry. Minimise cost over pitch alone and the optimizer always runs
to the shallowest pitch the covering permits. That is a lookup in a
minimum-slope table, not a search.

So an optimizer is only worth building once the model is rich enough to have a
non-trivial answer. Below is what that takes.

### What actually makes it non-trivial

**Discontinuities at product thresholds.** This is the strongest reason to
search. Below 4:12 (18.4°), clay and concrete tile need doubled underlayment or
a full ice-and-water shield, so cost *jumps*. There is a genuine local minimum
on each side, and which wins depends on the footprint. Waste tiers and timber
section jumps behave the same way.

**Batten gauge runs the other way.** Shallower pitch needs more headlap, which
tightens the gauge and *increases* batten linear metres. One of the few terms
that gets cheaper as you steepen.

**Discrete topology.** Per-edge hip-vs-gable is a `2^n` space that interacts
with the skeleton's structure, and it's where the money is: a gable removes a
hip's cut waste and flashing but adds wall and a verge. Footprint decomposition
is bigger still — it can eliminate valleys entirely, and valleys are the most
expensive linear item per metre.

**Structure — weaker than it first appears.** Snow load is specified per m² of
*plan*, so for rafters at spacing `s` over plan span `L`, the bending moment is
`q·s·L²/8`: the pitch terms cancel exactly. Pitch enters only through Eurocode's
shape coefficient `μ₁`, flat at 0.8 to 30°, then falling linearly to zero at
60°. Dead load, being per m² of *slope*, grows as `1/cos θ` throughout.

So below 30° there is no structural benefit to steepening at all. And
EN 1991-1-3 forbids reducing `μ₁` below 0.8 wherever a parapet or snow guard
exists, which removes the effect entirely on many real buildings. Do not build
the cost model around a snow-driven optimum.

### Design variables, if we build it

Continuous: per-edge pitch (primary), eaves overhang, eave height.

Discrete: gable mask per edge (binary), covering material (categorical, ~5,
and it sets the pitch floor so it interacts with everything), rafter spacing,
rafter section from a catalogue, ridge orientation, footprint decomposition.

Explicitly rejected: solar tilt as an objective. The yield curve is far too flat
— under 2% loss at ±10° from optimum — so it cannot move the answer and only
adds noise. Use it as a constraint band if a client insists.

### Method

**Not Bayesian optimization.** BO exists to avoid expensive evaluations; ours
are milliseconds. Fitting a Gaussian process is `O(N³)` and would cost more than
the evaluations it saves. This was checked specifically and the literature
agrees: evolution strategies overtake BO once the budget passes a few hundred
evaluations, which we'd cross in under a second.

Recommended shape, in order:

1. **A Sobol sweep first, before any optimizer.** A few thousand points costs
   seconds and tells you whether the landscape has structure at all. If cost
   turns out monotone in every angle, stop and report the boundary solution
   honestly instead of dressing it up.
2. **Enumerate the discrete configurations** in an outer loop rather than
   letting a GA search them. There are few plausible values and the full ranking
   is worth having for explaining results.
3. **CMA-ES on the continuous pitches** in the inner loop, BIPOP restarts,
   `sigma0` about a quarter of the range.
4. **Derivative-free polish** — Nelder-Mead, not L-BFGS-B, whose finite
   differences would straddle topology boundaries.

Parameterise in **degrees, never in weights**. `weight = cot(pitch)` blows up as
pitch approaches zero and destroys any optimizer's step-size adaptation.

### Exploitable structure

Within a fixed skeleton topology the takeoff is *real-analytic* in the pitches:
skeleton nodes solve 3×3 linear systems, so node coordinates are rational
functions of the design variables and everything downstream is smooth. Topology
is constant on open cells of weight-space separated by a measure-zero set of
critical weights.

The practical exploit is cheap: **hash the skeleton's combinatorial structure**
(sorted arc adjacency) on every evaluation. A changed hash means a crossed cell
boundary. That is both the signal for shrinking a polish step and the best
diagnostic for how rugged the landscape really is.

Enumerating cells analytically is *not* worth it — no published algorithm exists
for weighted skeletons, and deriving one is original research.

### Two prerequisites in the core library

Both belong in the skeleton implementation, not the optimizer, and both are
cheaper to build in from the start than to retrofit:

- **Deterministic tie-breaking at degeneracies.** Ambiguous events have several
  valid resolutions. Non-deterministic choice presents to an optimizer as
  objective noise, and will look like a hard search problem when it is actually
  a bug.
- **Finite penalties on failure, never exceptions or NaN.** Kelly and Wonka hit
  skeleton failures even on a 6,000-building dataset. An optimizer will find
  every degenerate configuration a footprint admits.

### Multi-objective

The second objective should be **usable attic volume above 2.0 m headroom** —
objective, computable from the roof solid, and the actual tension in every real
roof conversation. `pymoo`'s `MixedVariableGA` maps cleanly onto the variable
structure. Cap at three objectives.

The output worth building toward is a **trade-off curve with the binding
constraint named**, not a single optimum. "You're paying €4,200 for clay tile's
18° minimum; metal at 8° saves it but changes how the building reads" is worth
more to an architect than any single number.

### Prior art

`Point2WSS` (ISPRS 2026) uses exactly our parameterisation — footprint plus one
angle per edge — but *predicts* angles from point clouds rather than optimising
them. No published work optimises straight-skeleton weights against a design
objective. That's a real gap.

---

## 2. Roof types beyond hip and gable

Half-hips, knee-walls, gablets and gambrels need **additive weights** (Held &
Palfrader): a delay before an edge starts moving, so the wall rises vertically
to a set height and only then slopes. Their paper shows this also produces
ridges perpendicular to long walls, which no unweighted skeleton can do.

Deliberately out of scope, but reachable — ADR-0001 chose our own implementation
partly to keep this possible. CGAL would have foreclosed it permanently.

---

## 3. Web application

Unresolved on purpose. The core library must not assume an answer: data in,
data out, no I/O, no framework.

Once there is something worth showing, the options are a Python server
(simplest, now that zero hosting cost isn't required), Pyodide (no server, but
ships a large runtime), or a port of the core to TypeScript.

For hosting a static build, Cloudflare Pages remains the standout — unlimited
bandwidth and requests on the free tier where Netlify, Vercel and GitHub Pages
all cap at 100 GB/month — with a 25 MB per-file limit to design around.

---

## 4. Interoperability

Ranked by how much they'd change adoption:

- **`.3dm` export** — the highest-value item by some distance. `rhino3dm`'s
  WebAssembly build can write 3dm files, so results could land back in Rhino
  instead of being remodelled by hand. Note two known traps: copy the result of
  `toByteArray()` into a fresh `Uint8Array`, and set render meshes explicitly
  since rhino3dm does no tessellation.
- **DXF import** of footprints, since that's what already exists on his disk.
- **glTF / OBJ** export, trivial and useful for any viewer.
- **CSV / XLSX** takeoff export.
- **IFC** — only if someone actually asks.

---

## 5. Honest limitation to document

Ren et al. (SIGGRAPH Asia 2021) show the straight skeleton cannot represent a
roof face spanning multiple outline edges, and invents spurious vertices near
some outlines. Roofs with the same outline can have different valid styles. Our
search space is a strict subset of buildable roofs, and the documentation should
say so rather than implying completeness.
