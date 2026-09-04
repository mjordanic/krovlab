"""Corpus of footprints as regression fixtures, reported as a pass rate.

Fixtures are drop-in files. Each is fed through ``roof`` and the
invariant harness; a recorded topology hash catches a structure change
that still satisfies every invariant. Unroofable fixtures record an
expected failure and are counted separately.
"""

from pathlib import Path

import pytest

from corpus import (
    CORPUS_DIR,
    REPORT_PATH,
    Fixture,
    FixtureResult,
    load_fixtures,
    render_report,
    run_fixture,
)

_COMMITTED = load_fixtures(CORPUS_DIR)

SQUARE_TOML = (
    "footprint = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]\n"
    "pitch = 45.0\n"
)
BOWTIE_TOML = (
    "footprint = [[0.0, 0.0], [10.0, 10.0], [10.0, 0.0], [0.0, 10.0]]\n"
    "pitch = 45.0\n"
    'expected_failure = "self_intersection"\n'
)


def test_dropping_a_toml_file_is_enough_to_add_a_fixture(tmp_path: Path) -> None:
    (tmp_path / "square.toml").write_text(SQUARE_TOML)
    loaded = load_fixtures(tmp_path)
    assert [item.name for item in loaded] == ["square"]
    assert loaded[0].footprint == [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
    ]
    assert loaded[0].pitch == 45.0
    assert loaded[0].holes is None
    assert loaded[0].overhang == 0.0
    assert loaded[0].expected_failure is None
    assert loaded[0].topology_hash is None


def test_a_passing_fixture_is_run_through_the_invariant_harness(
    tmp_path: Path,
) -> None:
    (tmp_path / "square.toml").write_text(SQUARE_TOML)
    [fixture] = load_fixtures(tmp_path)
    result = run_fixture(fixture)
    assert result.outcome == "pass"
    assert result.property is None
    assert result.topology_hash is not None


def test_an_expected_failure_is_counted_separately_from_an_invariant_failure(
    tmp_path: Path,
) -> None:
    (tmp_path / "bowtie.toml").write_text(BOWTIE_TOML)
    [fixture] = load_fixtures(tmp_path)
    result = run_fixture(fixture)
    assert result.outcome == "expected_failure"
    assert result.property == "self_intersection"


def test_a_recorded_topology_hash_mismatch_is_caught(tmp_path: Path) -> None:
    (tmp_path / "square.toml").write_text(
        SQUARE_TOML + 'topology_hash = "not-the-real-hash"\n'
    )
    [fixture] = load_fixtures(tmp_path)
    result = run_fixture(fixture)
    assert result.outcome == "hash_mismatch"
    assert result.property == "topology hash"
    assert result.topology_hash != "not-the-real-hash"


def test_report_states_a_pass_rate_and_names_the_property_that_broke(
    tmp_path: Path,
) -> None:
    (tmp_path / "square.toml").write_text(SQUARE_TOML)
    (tmp_path / "square-stale-hash.toml").write_text(
        SQUARE_TOML + 'topology_hash = "not-the-real-hash"\n'
    )
    (tmp_path / "bowtie.toml").write_text(BOWTIE_TOML)
    results = [run_fixture(item) for item in load_fixtures(tmp_path)]
    report = render_report(results)
    assert "1/2" in report
    assert "square-stale-hash" in report
    assert "topology hash" in report
    assert "bowtie" in report
    assert "self_intersection" in report
    assert "expected failure" in report.lower() or "unroofable" in report.lower()


def test_report_names_an_invariant_failure_as_the_broken_property() -> None:
    report = render_report(
        [
            FixtureResult(
                name="warped",
                outcome="invariant_failure",
                property="every face is planar",
                topology_hash=None,
                detail="every face is planar: face 0 has a vertex 0.01 m off the plane",
            )
        ]
    )
    assert "0/1" in report
    assert "warped" in report
    assert "every face is planar" in report


def test_the_committed_corpus_is_discovered_from_the_fixtures_directory() -> None:
    names = {item.name for item in _COMMITTED}
    assert names, "drop a .toml file in tests/fixtures/footprints/"
    discovered = {path.stem for path in CORPUS_DIR.glob("*.toml")}
    assert names == discovered


@pytest.mark.parametrize("fixture", _COMMITTED, ids=lambda item: item.name)
def test_committed_fixture(fixture: Fixture) -> None:
    result = run_fixture(fixture)
    if fixture.expected_failure is not None:
        assert result.outcome == "expected_failure", result.detail
        assert result.property == fixture.expected_failure
        return
    assert result.outcome == "pass", result.detail
    recorded = fixture.topology_hash
    if recorded is not None:
        assert result.topology_hash == recorded


def test_committed_report_matches_the_live_corpus() -> None:
    results = [run_fixture(item) for item in _COMMITTED]
    assert REPORT_PATH.read_text() == render_report(results)
