# 01: Eave height on a single roof

**What to build:** The architect can lift one roof by a plate height. The
one-footprint function still roofs a single cell; an optional eave height in
metres above datum is added to every node's height afterwards. Terrain is still
assessed with eaves at height zero, then the constant is applied. Default eave
height is zero, so the 10 × 6 m rectangle at 45° still has ridge height 3 m.

On the page, one eave-height field posts with the existing form. Setting it to
7 m on that rectangle reports ridge height 10 m, still a terrain, with plan and
3D. Callers who only use the one-footprint function still do not see a cell
index on faces.

This is the lift primitive. Composition of several cells is ticket 02.

**Blocked by:** None (can start immediately)

**Status:** done

**Stories:** 7 (one-footprint call unchanged except the new optional height), 8,
25 (metres), 27, 35

**Prior art:** Assess-then-lift and "eave height on the one-footprint call" in
the feature PRD. Worked numbers: 10 × 6 m at 45° has a 4 m ridge at height 3 m;
lifting by 7 m must put that ridge at 10 m. Validity assessment already runs at
eave height zero. Flask test client against the form page; default GET from the
form-server spec. Faces on a single roof must not grow a cell index.

- [x] `roof` with default eave height still returns the 10 × 6 m rectangle at
      45° as a terrain with ridge height 3 m
- [x] `roof` with eave height 7 m on that rectangle is a terrain whose ridge
      height is 10 m and whose plan areas are unchanged
- [x] Terrain / validity is decided before the lift; a documented non-terrain
      stays a non-terrain after a non-zero eave height
- [x] POST of the default rectangle with eave height 7 m reports ridge height
      10 m, shows plan and 3D, and does not 500
- [x] GET with no eave height posted still shows ridge height 3 m
- [x] Faces returned by the one-footprint function have no cell index

## Comments

Assess-then-lift lives in `_roof_from_skeleton`: validity runs on eave-plane
nodes, then a constant is added. The wavefront is unchanged. The form posts
`eave_height` next to overhang; missing or blank is zero.
