from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ConstraintMetrics:
    on_sphere: float
    equilateral: float
    planar: float
    shortest_edge: float
    longest_edge: float


def calculate_metrics(
    positions: np.ndarray,
    edge_indices: np.ndarray,
    face_indices: tuple[np.ndarray, ...],
) -> ConstraintMetrics:
    edge_lengths = calculate_edge_lengths(positions, edge_indices)
    face_errors = np.array(
        [calculate_face_planarity_error(positions[face]) for face in face_indices],
        dtype=np.float64,
    )
    radii = np.linalg.norm(positions, axis=1)

    return ConstraintMetrics(
        on_sphere=float(np.max(np.abs(radii - 1.0))),
        equilateral=float(np.max(edge_lengths) - np.min(edge_lengths)),
        planar=float(np.max(face_errors)),
        shortest_edge=float(np.min(edge_lengths)),
        longest_edge=float(np.max(edge_lengths)),
    )


def calculate_edge_lengths(positions: np.ndarray, edge_indices: np.ndarray) -> np.ndarray:
    deltas = positions[edge_indices[:, 0]] - positions[edge_indices[:, 1]]
    return np.linalg.norm(deltas, axis=1)


def calculate_face_planarity_error(face_positions: np.ndarray) -> float:
    centred = face_positions - np.mean(face_positions, axis=0)
    _, singular_values, _ = np.linalg.svd(centred, full_matrices=False)
    return float(singular_values[-1] / np.sqrt(len(face_positions)))
