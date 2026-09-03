"""Event log and topology hash, through the public seam.

The roof stays a value about faces, arcs and nodes. Events are opt-in.
The hash is of combinatorial structure, not coordinates.
"""

import subprocess
import sys

import pytest
from hypothesis import given, settings

from generation import PITCHES, footprints
from krovlab import Failure, Roof, roof, topology_hash

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
RECTANGLE = [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)]

_SETTINGS = settings(max_examples=40, deadline=None)


def test_default_roof_call_is_not_handed_an_event_log() -> None:
    result = roof(SQUARE, 45.0)
    assert isinstance(result, Roof)
    assert "events" not in Roof.__dataclass_fields__


def test_square_event_log_lists_edge_events_at_the_apex_height() -> None:
    result = roof(SQUARE, 45.0, events=True)
    assert not isinstance(result, Failure)
    built, events = result
    assert isinstance(built, Roof)
    assert len(events) > 0
    for event in events:
        assert event.kind == "edge"
        assert event.time == pytest.approx(5.0)
        assert len(event.edges) > 0
        assert len(event.vertices) > 0
    times = [event.time for event in events]
    assert times == sorted(times)


def test_rectangle_event_log_lists_edge_events_at_ridge_height() -> None:
    result = roof(RECTANGLE, 45.0, events=True)
    assert not isinstance(result, Failure)
    built, events = result
    assert isinstance(built, Roof)
    assert len(events) > 0
    for event in events:
        assert event.kind == "edge"
        assert event.time == pytest.approx(3.0)
        assert event.edges
        assert event.vertices
        for edge in event.edges:
            assert edge in range(4)
        for vertex in event.vertices:
            assert vertex in range(len(built.nodes))
        assert any(
            built.nodes[vertex].height == pytest.approx(event.time)
            for vertex in event.vertices
        )
    times = [event.time for event in events]
    assert times == sorted(times)


def test_events_true_on_unroofable_input_is_still_a_failure() -> None:
    result = roof([(0.0, 0.0)], 45.0, events=True)
    assert isinstance(result, Failure)


def test_clockwise_event_edges_are_caller_edge_indices() -> None:
    clockwise = list(reversed(SQUARE))
    result = roof(clockwise, 45.0, events=True)
    assert not isinstance(result, Failure)
    _built, events = result
    vanishing = {event.edges[1] for event in events}
    assert vanishing <= {0, 1, 2, 3}
    assert len(vanishing) > 0


def test_topology_hash_is_stable_across_runs() -> None:
    first = roof(RECTANGLE, 45.0)
    second = roof(RECTANGLE, 45.0)
    assert isinstance(first, Roof)
    assert isinstance(second, Roof)
    assert topology_hash(first) == topology_hash(second)


def test_topology_hash_is_stable_across_processes() -> None:
    built = roof(RECTANGLE, 45.0)
    assert isinstance(built, Roof)
    here = topology_hash(built)
    code = (
        "from krovlab import roof, topology_hash; "
        "print(topology_hash(roof([(0,0),(10,0),(10,6),(0,6)], 45)))"
    )
    out = subprocess.check_output([sys.executable, "-c", code], text=True).strip()
    assert out == here


def test_perturbing_a_vertex_without_changing_which_faces_meet_keeps_the_hash() -> None:
    built = roof(RECTANGLE, 45.0)
    # Shift a corner in y so the old ridge is no longer horizontal (its
    # arc kind may flip) while the same faces still meet at the same nodes.
    perturbed = roof(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 6.05), (0.0, 6.0)],
        45.0,
    )
    assert isinstance(built, Roof)
    assert isinstance(perturbed, Roof)
    assert topology_hash(built) == topology_hash(perturbed)


def test_changing_which_faces_meet_changes_the_hash() -> None:
    pyramid = roof(SQUARE, 45.0)
    hipped = roof(RECTANGLE, 45.0)
    assert isinstance(pyramid, Roof)
    assert isinstance(hipped, Roof)
    assert topology_hash(pyramid) != topology_hash(hipped)


def test_topology_hash_ignores_coordinates() -> None:
    shallow = roof(SQUARE, 30.0)
    steep = roof(SQUARE, 60.0)
    assert isinstance(shallow, Roof)
    assert isinstance(steep, Roof)
    assert topology_hash(shallow) == topology_hash(steep)


@_SETTINGS
@given(footprints(), PITCHES)
def test_topology_hash_is_stable_for_generated_footprints(
    footprint: list[tuple[float, float]], pitch: float
) -> None:
    first = roof(footprint, pitch)
    second = roof(footprint, pitch)
    assert isinstance(first, Roof)
    assert isinstance(second, Roof)
    assert topology_hash(first) == topology_hash(second)
