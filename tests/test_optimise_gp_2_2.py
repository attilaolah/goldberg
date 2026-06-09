from goldberg_optimisation.optimise_gp_2_2 import (
    PRIORITY_PRECISION_TOLERANCE,
    TARGET_TOLERANCE,
    count_satisfied_targets,
    satisfies_priority_goal,
    satisfies_priority_precision_goal,
    select_best_candidate,
)


def test_current_report_matches_priority_strategy() -> None:
    import json

    with open("data/gp_2_2_optimisation_report.json") as report_file:
        report = json.load(report_file)

    assert report["priority_order"] == ["on_sphere", "equilateral", "planar"]
    assert report["satisfies_priority_goal"] is True
    assert report["satisfies_priority_precision_goal"] is True
    assert report["satisfies_target"] is False
    assert report["metrics"]["on_sphere"] <= PRIORITY_PRECISION_TOLERANCE
    assert report["metrics"]["equilateral"] <= PRIORITY_PRECISION_TOLERANCE
    assert report["metrics"]["equilateral"] <= 2e-16
    assert report["metrics"]["planar"] > TARGET_TOLERANCE


def test_count_satisfied_targets_uses_headline_metrics() -> None:
    metrics = {
        "on_sphere": TARGET_TOLERANCE / 2.0,
        "equilateral": TARGET_TOLERANCE / 2.0,
        "planar": TARGET_TOLERANCE * 2.0,
        "shortest_edge": 1.0,
        "longest_edge": 1.0,
    }

    assert count_satisfied_targets(metrics) == 2


def test_select_best_candidate_uses_metric_priority_order() -> None:
    better_planarity_only = {
        "stage": "better_planarity_only",
        "metrics": {
            "on_sphere": TARGET_TOLERANCE / 2.0,
            "equilateral": TARGET_TOLERANCE * 3.0,
            "planar": TARGET_TOLERANCE / 2.0,
        },
        "satisfied_target_count": 1,
    }
    better_equilateral = {
        "stage": "better_equilateral",
        "metrics": {
            "on_sphere": TARGET_TOLERANCE / 2.0,
            "equilateral": TARGET_TOLERANCE / 2.0,
            "planar": TARGET_TOLERANCE * 100.0,
        },
        "satisfied_target_count": 2,
    }

    assert select_best_candidate([better_planarity_only, better_equilateral])["stage"] == "better_equilateral"


def test_select_best_candidate_requires_near_sphere_first() -> None:
    off_sphere = {
        "stage": "off_sphere",
        "metrics": {
            "on_sphere": TARGET_TOLERANCE * 2.0,
            "equilateral": 0.0,
            "planar": 0.0,
        },
        "satisfied_target_count": 2,
    }
    on_sphere = {
        "stage": "on_sphere",
        "metrics": {
            "on_sphere": TARGET_TOLERANCE / 2.0,
            "equilateral": TARGET_TOLERANCE * 100.0,
            "planar": TARGET_TOLERANCE * 100.0,
        },
        "satisfied_target_count": 1,
    }

    assert select_best_candidate([off_sphere, on_sphere])["stage"] == "on_sphere"


def test_priority_goal_requires_sphere_and_equilateral() -> None:
    metrics = {
        "on_sphere": TARGET_TOLERANCE / 2.0,
        "equilateral": TARGET_TOLERANCE / 2.0,
        "planar": TARGET_TOLERANCE * 100.0,
    }

    assert satisfies_priority_goal(metrics)


def test_priority_precision_goal_requires_tighter_sphere_and_equilateral() -> None:
    metrics = {
        "on_sphere": PRIORITY_PRECISION_TOLERANCE / 2.0,
        "equilateral": PRIORITY_PRECISION_TOLERANCE / 2.0,
        "planar": TARGET_TOLERANCE * 100.0,
    }

    assert satisfies_priority_precision_goal(metrics)
