import numpy as np
from scipy.linalg import eigh

from goldberg_optimisation.topology import Topology


def spectral_initial_positions(topology: Topology) -> np.ndarray:
    """Return deterministic unit-sphere positions from Laplacian eigenvectors."""

    label_to_index = {label: index for index, label in enumerate(topology.labels)}
    vertex_count = len(topology.labels)
    adjacency = np.zeros((vertex_count, vertex_count), dtype=np.float64)
    for left, right in topology.edges:
        left_index = label_to_index[left]
        right_index = label_to_index[right]
        adjacency[left_index, right_index] = 1.0
        adjacency[right_index, left_index] = 1.0

    degree = np.diag(adjacency.sum(axis=1))
    laplacian = degree - adjacency
    _, eigenvectors = eigh(laplacian)
    positions = eigenvectors[:, 1:4].copy()
    positions = _orient_positions(positions, topology.labels)
    return _normalise_rows(positions)


def _orient_positions(positions: np.ndarray, labels: tuple[str, ...]) -> np.ndarray:
    oriented = positions.copy()
    label_to_index = {label: index for index, label in enumerate(labels)}

    north = oriented[label_to_index["NA1"]]
    if north[2] < 0:
        oriented[:, 2] *= -1.0

    east_reference = oriented[label_to_index["N1A1"]]
    if east_reference[0] < 0:
        oriented[:, 0] *= -1.0

    if np.linalg.det(oriented[[label_to_index["NA1"], label_to_index["N1A1"], label_to_index["S1A1"]]]) < 0:
        oriented[:, 1] *= -1.0

    return oriented


def _normalise_rows(positions: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(positions, axis=1)
    return positions / norms[:, np.newaxis]
