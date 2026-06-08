from goldberg_optimisation.optimise_gp_2_2 import (
    TARGET_TOLERANCE,
    count_satisfied_targets,
    select_best_candidate,
)


def test_count_satisfied_targets_uses_headline_metrics() -> None:
    metrics = {
        "on_sphere": TARGET_TOLERANCE / 2.0,
        "equilateral": TARGET_TOLERANCE / 2.0,
        "planar": TARGET_TOLERANCE * 2.0,
        "shortest_edge": 1.0,
        "longest_edge": 1.0,
    }

    assert count_satisfied_targets(metrics) == 2


def test_select_best_candidate_prefers_more_satisfied_targets() -> None:
    one_target = {
        "stage": "one_target",
        "metrics": {
            "on_sphere": TARGET_TOLERANCE / 2.0,
            "equilateral": TARGET_TOLERANCE * 2.0,
            "planar": TARGET_TOLERANCE * 2.0,
        },
        "satisfied_target_count": 1,
    }
    two_targets = {
        "stage": "two_targets",
        "metrics": {
            "on_sphere": TARGET_TOLERANCE / 2.0,
            "equilateral": TARGET_TOLERANCE / 2.0,
            "planar": TARGET_TOLERANCE * 2.0,
        },
        "satisfied_target_count": 2,
    }

    assert select_best_candidate([one_target, two_targets])["stage"] == "two_targets"

