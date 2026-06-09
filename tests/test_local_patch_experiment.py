import json

from goldberg_optimisation.local_patch_experiment import EXACT_TOLERANCE, OUTPUT_PATH


def test_local_patch_experiment_report_records_growth_limit() -> None:
    report = json.loads(OUTPUT_PATH.read_text())
    results = {result["name"]: result for result in report["results"]}

    assert report["exact_tolerance"] == EXACT_TOLERANCE
    assert results["pentagon"]["exact"] is True
    assert results["pentagon_plus_one_hexagon"]["exact"] is True
    assert results["pentagon_plus_two_adjacent_hexagons"]["exact"] is False
    assert results["pentagon_plus_full_hexagon_ring"]["exact"] is False
    assert results["full_ring_plus_best_outer_face"]["exact"] is False

