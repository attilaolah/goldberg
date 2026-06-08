import numpy as np

from goldberg_optimisation.metrics import (
    calculate_edge_lengths,
    calculate_face_planarity_error,
    calculate_metrics,
)


def test_on_sphere_metric_is_zero_for_normalised_points() -> None:
    positions = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
    )
    edge_indices = np.array([[0, 1], [1, 2], [0, 2]])
    face_indices = (np.array([0, 1, 2]),)

    metrics = calculate_metrics(positions, edge_indices, face_indices)

    assert metrics.on_sphere == 0.0


def test_edge_lengths_match_for_equilateral_triangle() -> None:
    positions = np.array(
        [
            [1.0, 0.0, 0.0],
            [-0.5, np.sqrt(3.0) / 2.0, 0.0],
            [-0.5, -np.sqrt(3.0) / 2.0, 0.0],
        ],
    )
    edge_indices = np.array([[0, 1], [1, 2], [0, 2]])

    edge_lengths = calculate_edge_lengths(positions, edge_indices)

    assert np.max(edge_lengths) - np.min(edge_lengths) < 1e-15


def test_planarity_error_is_zero_for_coplanar_points() -> None:
    positions = np.array(
        [
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
            [0.0, 1.0, 1.0],
        ],
    )

    assert calculate_face_planarity_error(positions) < 1e-15


def test_planarity_error_detects_warped_points() -> None:
    positions = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.1],
        ],
    )

    assert calculate_face_planarity_error(positions) > 0.0

