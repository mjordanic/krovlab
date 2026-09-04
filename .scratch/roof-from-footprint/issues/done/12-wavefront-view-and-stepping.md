# 12: Wavefront view at a chosen time, and stepping through it

**What to build:** The developer renders the wavefront as it was at a chosen
time, and steps through it at successive times, watching the propagation that
produced the skeleton. When a roof comes out wrong he uses this to find the
exact event where it went wrong — the event log from ticket 04 tells him what
happened, this tells him what it looked like.

Because the wavefront rises at unit rate as it propagates, a time is also a
height: stepping through times is walking up the roof.

**Blocked by:** 04, 05

**Status:** done

**Prior art:** Ticket 04 exposed the processed event sequence; the times in that
log are the interesting times to render, so the two should agree on what an
event is and when it happened. Ticket 05 established the visualisation module
and its conventions. The feature PRD's user stories 22 and 23 are the source,
and ADR-0001 lists exposing the wavefront at intermediate times among the things
owning the algorithm buys us. `wavefront`, `event` and `time` are glossary terms
in `CONTEXT.md`, which notes that the time a node is created is its height.

- [x] The wavefront at a given time renders over the footprint
- [x] Stepping through successive times produces a sequence of views a developer
      can page through
- [x] Event times from ticket 04's log are reachable as step points, so the
      developer can land exactly on an event rather than near it
- [x] A time past the end of the propagation, and a negative time, both behave
      sensibly rather than erroring
- [x] The view saves as a self-contained HTML file, like the other views
- [x] The core package still imports nothing third-party
- [x] Smoke-tested only: the figures build
