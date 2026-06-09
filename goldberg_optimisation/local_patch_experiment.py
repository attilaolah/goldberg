import json
from collections import defaultdict
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import least_squares

from goldberg_optimisation.metrics import calculate_metrics
from goldberg_optimisation.topology import PROJECT_ROOT, Topology, load_topology


INPUT_VERTICES_PATH = PROJECT_ROOT / "data" / "gp_2_2_optimised_vertices.json"
INPUT_REPORT_PATH = PROJECT_ROOT / "data" / "gp_2_2_optimisation_report.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "gp_2_2_local_patch_experiment.json"
EXACT_TOLERANCE = 1e-12


@dataclass(frozen=True)
class PatchScenario:
    name: str
    face_indices: tuple[int, ...]
    description: str


def main() -> None:
    topology = load_topology()
    face_adjacency = build_face_adjacency(topology.faces)
    centre_face_index = topology.faces.index(tuple(f"NA{index}" for index in range(1, 6)))
    ring = tuple(sorted(face_adjacency[centre_face_index], key=lambda index: topology.faces[index]))
    outer = tuple(
        sorted(
            set().union(*(face_adjacency[face_index] for face_index in ring)) - set(ring) - {centre_face_index},
            key=lambda index: topology.faces[index],
        ),
    )

    scenarios = [
        PatchScenario("pentagon", (centre_face_index,), "The central N pentagon only."),
        PatchScenario(
            "pentagon_plus_one_hexagon",
            (centre_face_index, ring[0]),
            "The central N pentagon plus one neighbouring hexagon.",
        ),
        PatchScenario(
            "pentagon_plus_two_adjacent_hexagons",
            (centre_face_index, ring[0], ring[1]),
            "The central N pentagon plus two neighbouring hexagons that meet at NA1.",
        ),
        PatchScenario(
            "pentagon_plus_full_hexagon_ring",
            (centre_face_index, *ring),
            "The central N pentagon plus all five neighbouring hexagons.",
        ),
    ]

    results = [run_scenario(topology, scenario) for scenario in scenarios]
    ring_plus_outer = [run_scenario(topology, PatchScenario("candidate", (centre_face_index, *ring, face_index), "candidate")) for face_index in outer]
    best_outer = min(ring_plus_outer, key=lambda result: result["worst_error"])
    best_outer["name"] = "full_ring_plus_best_outer_face"
    best_outer["description"] = "The full ring plus the best single additional adjacent face from the ten outer candidates."
    results.append(best_outer)

    output = {
        "name": "Goldberg GP(2,2) local patch experiment",
        "edge_target": load_edge_target(),
        "exact_tolerance": EXACT_TOLERANCE,
        "non_degenerate_rule": "All selected face edges are fitted to the global priority edge length to avoid collapsed zero-edge patches.",
        "results": results,
    }
    OUTPUT_PATH.write_text(f"{json.dumps(output, indent=2)}\n")

    for result in results:
        print(
            f"{result['name']}: exact={result['exact']} "
            f"faces={result['face_count']} vertices={result['vertex_count']} "
            f"worst={result['worst_error']:.3e}",
        )


def run_scenario(topology: Topology, scenario: PatchScenario) -> dict[str, object]:
    labels = tuple(sorted({label for face_index in scenario.face_indices for label in topology.faces[face_index]}, key=topology.labels.index))
    label_to_local = {label: index for index, label in enumerate(labels)}
    edges = np.array(
        [(label_to_local[left], label_to_local[right]) for left, right in build_face_edges(topology.faces, scenario.face_indices)],
        dtype=np.int64,
    )
    faces = tuple(np.array([label_to_local[label] for label in topology.faces[face_index]], dtype=np.int64) for face_index in scenario.face_indices)
    positions = optimise_patch(labels, edges, faces)
    metrics = calculate_metrics(positions, edges, faces)
    edge_lengths = np.linalg.norm(positions[edges[:, 0]] - positions[edges[:, 1]], axis=1)
    edge_target_error = float(np.max(np.abs(edge_lengths - load_edge_target())))
    worst_error = max(metrics.on_sphere, metrics.equilateral, metrics.planar, edge_target_error)

    return {
        "name": scenario.name,
        "description": scenario.description,
        "exact": worst_error <= EXACT_TOLERANCE,
        "face_count": len(scenario.face_indices),
        "vertex_count": len(labels),
        "edge_count": len(edges),
        "faces": [list(topology.faces[index]) for index in scenario.face_indices],
        "metrics": asdict(metrics),
        "edge_target_error": edge_target_error,
        "worst_error": worst_error,
    }


def optimise_patch(
    labels: tuple[str, ...],
    edges: np.ndarray,
    faces: tuple[np.ndarray, ...],
) -> np.ndarray:
    global_positions = load_positions()
    positions = np.array([global_positions[label] for label in labels], dtype=np.float64)
    planes = calculate_face_planes(positions, faces)
    variables = pack_variables(positions, planes)

    for _ in range(2):
        result = least_squares(
            patch_residuals,
            variables,
            args=(len(labels), edges, faces),
            jac="3-point",
            method="trf",
            x_scale="jac",
            ftol=1e-14,
            xtol=1e-14,
            gtol=1e-14,
            max_nfev=2000,
        )
        variables = result.x

    positions, _ = unpack_variables(variables, len(labels), len(faces))
    return positions


def patch_residuals(
    variables: np.ndarray,
    vertex_count: int,
    edges: np.ndarray,
    faces: tuple[np.ndarray, ...],
) -> np.ndarray:
    positions, planes = unpack_variables(variables, vertex_count, len(faces))
    sphere = np.linalg.norm(positions, axis=1) - 1.0
    edge_lengths = np.linalg.norm(positions[edges[:, 0]] - positions[edges[:, 1]], axis=1)
    edge_errors = edge_lengths - load_edge_target()
    planar = []
    for face, plane in zip(faces, planes, strict=True):
        planar.extend(positions[face] @ plane[:3] - plane[3])
    plane_norms = np.linalg.norm(planes[:, :3], axis=1) - 1.0
    return np.concatenate((sphere, edge_errors, np.array(planar), plane_norms))


def calculate_face_planes(
    positions: np.ndarray,
    faces: tuple[np.ndarray, ...],
) -> np.ndarray:
    planes = np.zeros((len(faces), 4), dtype=np.float64)
    for index, face in enumerate(faces):
        face_positions = positions[face]
        centre = np.mean(face_positions, axis=0)
        centred = face_positions - centre
        _, _, vh = np.linalg.svd(centred, full_matrices=False)
        normal = vh[-1]
        planes[index, :3] = normal
        planes[index, 3] = float(np.dot(normal, centre))
    return planes


def pack_variables(positions: np.ndarray, planes: np.ndarray) -> np.ndarray:
    return np.concatenate((positions.reshape(-1), planes.reshape(-1)))


def unpack_variables(
    variables: np.ndarray,
    vertex_count: int,
    face_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    positions = variables[: vertex_count * 3].reshape((vertex_count, 3))
    planes = variables[vertex_count * 3 :].reshape((face_count, 4))
    return positions, planes


def build_face_adjacency(faces: tuple[tuple[str, ...], ...]) -> dict[int, set[int]]:
    edge_to_faces: dict[tuple[str, str], list[int]] = defaultdict(list)
    for face_index, face in enumerate(faces):
        for edge in face_edges(face):
            edge_to_faces[edge].append(face_index)

    adjacency: dict[int, set[int]] = defaultdict(set)
    for face_indices in edge_to_faces.values():
        if len(face_indices) != 2:
            continue
        left, right = face_indices
        adjacency[left].add(right)
        adjacency[right].add(left)
    return adjacency


def build_face_edges(
    faces: tuple[tuple[str, ...], ...],
    face_indices: tuple[int, ...],
) -> tuple[tuple[str, str], ...]:
    edges = {edge for face_index in face_indices for edge in face_edges(faces[face_index])}
    return tuple(sorted(edges))


def face_edges(face: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    return tuple(tuple(sorted((label, face[(index + 1) % len(face)]))) for index, label in enumerate(face))


def load_positions() -> dict[str, list[float]]:
    return json.loads(INPUT_VERTICES_PATH.read_text())["vertices"]


def load_edge_target() -> float:
    return float(json.loads(INPUT_REPORT_PATH.read_text())["edge_length"])


if __name__ == "__main__":
    main()
