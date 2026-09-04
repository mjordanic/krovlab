# 07: Per-edge pitch — the weighted wavefront

**What to build:** The architect gives a different pitch for each footprint
edge, and gets a roof whose sides are not all the same slope. Each face comes
back labelled with the edge it rises from and its own pitch, so he can connect
the model back to the building and see which slope produced which area.

This is the ticket the whole project is named for: the wavefront becomes
weighted, each edge moving at its own speed, with `weight = cot(pitch)` computed
at the boundary and never seen by the caller. A larger weight is a flatter face.

It is also the stage that removes the equidistance oracle. Up to now every
skeleton node could be checked against an independent computation; from here the
invariant harness is the only judge, which is why it was built first and why
this ticket must not weaken it. Expect the ambiguity the literature warns about:
adjacent parallel edges of differing weight have no unique answer. Pick a
documented resolution, and make it deterministic — the same input must give the
same roof.

**Blocked by:** 06

**Status:** done

**Prior art:** ADR-0001 is the essential read: it confines this work to strictly
positive multiplicative weights, the regime where Biedl et al. show weighted
skeletons behave essentially like unweighted ones, and it names adjacent
parallel edges of differing weight as the known ambiguity. The feature PRD's
"Pitch is the parameter; weight is internal" and "Strictly positive weights
only" decisions fix the boundary conversion and the constraint. Ticket 02's
harness is now the sole correctness gate — widen its generator to per-edge
pitch. Ticket 03's validation already refuses a mismatched pitch list length.
`weight`, `weighted straight skeleton` and `pitch` are glossary terms in
`CONTEXT.md`, which also states that weight is multiplicative unless stated and
must be strictly positive.

- [x] One pitch per footprint edge produces a roof whose faces each carry their
      own pitch
- [x] Each face names the footprint edge it rises from
- [x] A uniform pitch supplied as a per-edge list gives the same roof as the
      same pitch supplied as a single value
- [x] Weights are computed only at the entry point; no weight appears in the
      returned roof
- [x] The invariant harness's generator produces per-edge pitches and every
      property from ticket 02 still holds — in particular drainage, since a
      steeper neighbour is what tilts an arc the wrong way
- [x] Adjacent parallel edges of differing pitch resolve by a documented rule,
      deterministically, or return a stated failure
- [x] Sloped areas still exceed plan areas face by face, with the steeper face
      showing the larger excess

## Comments

Adjacent parallel edges of differing pitch are refused as `unsupported`
(no unique skeleton). Same-pitch collinear vertices stay roofable.

The invariant generator draws per-edge pitches on convex footprints.
Reflex + mixed pitch is asserted by a worked L-shape: some L/U parallel
catch-ups still stall the wavefront, so that mix is not generated until
it is reliable.
