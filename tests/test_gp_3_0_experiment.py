import json

from goldberg_optimisation.gp_3_0_experiment import OUTPUT_PATH, TARGET_TOLERANCE


def test_gp_3_0_experiment_report_exists_and_has_variants() -> None:
    report = json.loads(OUTPUT_PATH.read_text())
    results = {result["name"]: result for result in report["results"]}

    assert report["target_tolerance"] == TARGET_TOLERANCE
    assert set(results) == {"strict_unit_sphere", "paper_commented_pnas_case"}
    assert all("metrics" in result for result in results.values())

