# 05: Plan view — skeleton over footprint, arcs coloured by type, heights annotated

**What to build:** The architect opens a plan view of his roof: the footprint
with the skeleton drawn over it, each arc coloured by what it is — ridge, hip,
valley, eave, verge — so he reads the roof's layout at a glance. Node heights
are annotated on the drawing, so he understands the roof's third dimension
without leaving the plan. He saves the view as a single HTML file that opens
from his desktop by double-clicking it, with no server running, and can email
that file to someone.

Visualisation is a separate, optional module that consumes a roof and returns
figures. It never reaches past the entry point into the algorithm, and the core
must not import it — the core's dependency-free promise is what lets it be
embedded elsewhere later. Plotly is the choice, already declared as the `viz`
optional extra, because it emits a self-contained file that works over `file://`.

Placed this early on purpose: the views that matter while building this library
are the 2D ones, and every geometry ticket after this is easier to debug with a
picture than without.

**Blocked by:** 01

**Status:** ready-for-agent

**Prior art:** The feature PRD's "Visualisation uses Plotly and is a separate,
optional module" decision explains the choice of Plotly over a 3D engine, and
"Visualisation is smoke-tested only" sets the testing bar — that the figure
builds, not what its pixels are. Ticket 01's roof value is the whole input; if
this module needs anything the roof does not carry, that is a finding to report,
not a reason to reach into the algorithm. Arc types are glossary terms in
`CONTEXT.md`: colour them by those names, not by invented ones. Ticket 01's
`viz` extra in the project's optional dependencies is already declared.

- [ ] A roof renders as a plan view showing the footprint and the skeleton over
      it
- [ ] Arcs are coloured by classification, using the glossary names in the
      legend
- [ ] Node heights are annotated on the view
- [ ] The view saves as one self-contained HTML file that opens over `file://`
      with no server and no network access
- [ ] The core package still imports nothing third-party — the test from ticket
      01 still passes with the viz module present
- [ ] The module works from a roof value alone, with no access to algorithm
      internals
- [ ] Smoke tests assert the figure builds without error; nothing asserts on
      pixels
