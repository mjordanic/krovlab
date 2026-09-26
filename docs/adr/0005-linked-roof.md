# 5. The experimental method is the linked roof

Date: 2026-09-26

## Status

Accepted. Supersedes the face-graph half of
[ADR 0004](0004-experimental-method-is-optional.md).

## Context

ADR 0004 added an optional unpitched method beside the straight skeleton.
That method predicted a face graph and lifted it. The visitor could not
say which wall drained to which ridge, and a move that was not already a
terrain was pulled back to the previous roof.

## Decision

The skeleton remains the default and the only core. `roof` and `project`
keep their arguments and their results.

The experimental method is `krovlab.links.roof_from_links`. The visitor
connects each wall to one apex or one whole ridge, each corner to an
allowed end, and a ridge end to another ridge end or an apex. The page
draws the faces those links describe. It does not guess hips, and it
does not rewrite a typed offset or height. A new example starts from
`links_from_skeleton`. Pitch is not an input. Gable, knee, gambrel,
holes, dormers, and extra cells are not inputs.

There is no face-adjacency network and no checkpoint. The core does not
import this module. `import krovlab` does not import it.

The help agent prefers the skeleton. On the linked roof it may add an
apex or a ridge and set height, offset, snap, and symmetry. It does not
connect walls, corners, or ridge ends.

## Consequences

Callers that want the skeleton keep calling `roof`. Callers that want
this method import `krovlab.links`. A roof that is not a terrain is
still returned, with the reason on `validity`.
