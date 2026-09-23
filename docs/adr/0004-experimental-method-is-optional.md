# 4. Experimental method is optional and unpitched

Date: 2026-09-23

## Status

Accepted.

## Context

ADR-0001 put the weighted straight skeleton in Python as the core, with no
third-party dependencies. ADR-0002 wrapped that core in a form server and
said the core does not grow a second entry point. ADR-0003 added in-page
help that fills the skeleton's knobs.

A face that covers several non-collinear walls, or a ridge layout that is
not the skeleton's, cannot occur on that path. Ren et al. 2021 lift a face
graph into a planar roof without taking a pitch. That method is useful, and
it is not a replacement for the skeleton.

## Decision

The skeleton remains the default and the only core. `roof` and `project`
keep their arguments and their results. The experimental method is a second
entry point, outside that core: one footprint, an optional overhang, an
optional eave height, and a face graph. It returns a Roof or a Failure. It
does not take a pitch. Overhang and eave height keep the meanings they have
on the skeleton.

The page offers the choice above the example catalog. Opening the page
selects the skeleton. The experimental path is opt-in. Gable, knee,
gambrel, holes, dormers, and extra cells are not inputs of this method.

This method may depend on PyTorch when a checkpoint predicts the graph. The
core does not import PyTorch. `import krovlab` does not import the
experimental module.

The help agent is unchanged. It still fills the skeleton's knobs.

## Consequences

A later reader must not fold the network into `roof` or pull PyTorch into
the core. Callers that want the skeleton keep calling `roof`. Callers that
want this method import it from `krovlab.experimental`.
