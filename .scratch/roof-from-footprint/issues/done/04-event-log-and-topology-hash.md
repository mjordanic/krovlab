# 04: Algorithm instrumentation — event log and topology hash

**What to build:** When a roof comes out wrong, the developer can see the
sequence of events the algorithm processed and find the one where it went wrong,
instead of guessing from the finished geometry. And he can tell, from a stable
hash of the roof's combinatorial structure, whether a change to his input
changed the roof's topology or only moved its geometry.

Both of these exist because we own the algorithm rather than calling a library,
and ADR-0001 counted them among the compensations for that. They are also the
tools the next ticket needs: split events are where implementations break, and
debugging them from output geometry alone is miserable.

The event log is inspectable but not part of the roof's meaning — the roof stays
a value about faces, arcs and nodes. The hash covers structure only: which faces
meet which arcs at which nodes, not their coordinates. Two roofs that differ
only in a vertex position must hash the same; two that differ in which faces
meet must not.

**Blocked by:** 01

**Status:** done

**Prior art:** ADR-0001's Consequences section lists the event log and the
topology hash as things reachable precisely because there is no library
boundary. The feature PRD's "The returned roof is a value, not a drawing"
decision constrains where this can live — instrumentation must not turn the roof
into a debugging artifact. `event`, `wavefront` and `time` are glossary terms in
`CONTEXT.md`; note that an event's time is a height, which is what makes the log
readable against the finished roof. Ticket 02's determinism property is the
natural companion test for the hash.

- [x] The events the algorithm processed can be inspected after a roof is
      produced, in order, each identifying its kind, its time and the wavefront
      vertices or edges it involved
- [x] The hash is stable across runs and across processes for the same input
- [x] Perturbing a footprint vertex slightly, without changing which faces meet,
      leaves the hash unchanged
- [x] Changing the footprint so that different faces meet changes the hash
- [x] The event log is opt-in or otherwise kept out of the roof's core meaning,
      so callers computing with a roof are not handed debugging state
