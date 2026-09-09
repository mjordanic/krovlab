# 04: Plan as the cell editor

**What to build:** The architect draws cells on the plan instead of typing a
ring to start. Click vertices of the active cell, close the ring, add another
cell the same way, select a cell and set its eave height, click an edge to set
pitch or mark a gable, delete a cell drawn by mistake.

The millimetre tables stay in sync both ways: the drawing writes them, and
editing a table cell moves the corresponding vertex. Submit remains one form
POST of the existing page. No JSON API and no fetch of roofs. Extra page script
is expected; a second frontend stack is not.

The 5 m / 7 m pair drawn and posted reports the same ridge height and sloped
area as `project` in Python. Default GET is still the 10 × 6 m rectangle at 45°.

**Blocked by:** 02 project of cells

**Status:** ready-for-agent

**Complexity:** high

**Stories:** 28, 29, 30, 31, 32, 33, 34, 45 (finishes: canvas writes fields)

**Prior art:** Feature PRD "The plan is the editor; the table is the inspector"
and ADR-0002 (form POST, no JSON API). Existing form fields for one ring;
ticket 02's multi-cell fields are what the canvas must write. Flask test client
asserts posted fields and describe numbers, not CSS or pixels. Usability test in
the PRD: the second cell must exist without typing twelve numbers first.

- [ ] Clicking vertices and closing a ring creates a cell whose tables match
      those coordinates
- [ ] A second cell can be drawn as a second polygon without inserting rows
      into the first
- [ ] Selecting a cell and setting eave height posts that height on that cell
- [ ] Clicking an edge sets its pitch or marks a gable
- [ ] Editing a table vertex moves the vertex on the plan, and drawing updates
      the table
- [ ] A cell can be deleted
- [ ] Submit is still POST of the page; no JSON API
- [ ] Drawing and posting the 5 m / 7 m pair reports the same ridge height and
      sloped area as `project` in Python
- [ ] Default GET is still the 10 × 6 m rectangle at 45° with ridge height 3 m
- [ ] HTTP tests do not assert on CSS or pixels
