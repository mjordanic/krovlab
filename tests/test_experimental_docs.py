"""README for the linked roof.

The seam is the tracked README section a reader sees.
"""

from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_describes_the_linked_roof() -> None:
    text = README.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "roof_from_links" in text
    assert "links_from_skeleton" in text
    assert "footprint" in lowered
    assert "overhang" in lowered
    assert "eave height" in lowered or "eave_height" in text
    assert "does not take a pitch" in lowered
    assert "keep the skeleton" in lowered
    assert "graph network" not in lowered
    assert "roof_from_face_graph" not in text
    assert "ren_gnn" not in text
