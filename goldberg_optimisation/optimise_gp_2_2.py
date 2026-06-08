import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from goldberg_optimisation.initial_positions import spectral_initial_positions
from goldberg_optimisation.metrics import calculate_edge_lengths, calculate_metrics
from goldberg_optimisation.topology import PROJECT_ROOT, Topology, load_topology


OPTIMISED_VERTICES_PATH = PROJECT_ROOT / "data" / "gp_2_2_optimised_vertices.json"
OPTIMISATION_REPORT_PATH = PROJECT_ROOT / "data" / "gp_2_2_optimisation_report.json"
TARGET_TOLERANCE = 1e-10


@dataclass(frozen=True)
class OptimisationStage:
    name: str
    sphere_weight: float
    edge_weight: float
    planar_weight: float
    max_evaluations: int


STAGES = (
    OptimisationStage("sphere_and_edges", 10.0, 10.0, 0.0, 400),
    OptimisationStage("add_planarity", 10.0, 10.0, 1.0, 800),
    OptimisationStage("tighten_planarity", 50.0, 50.0, 10.0, 1200),
    OptimisationStage("final_polish", 100.0, 100.0, 100.0, 2000),
)


def main() -> None:
    topology = load_topology()
    result = optimise(topology)
    write_outputs(topology, result)

    metrics = result["metrics"]
    print("Optimisation complete")
    print(f"on_sphere:   {metrics['on_sphere']:.16e}")
    print(f"equilateral: {metrics['equilateral']:.16e}")
    print(f"planar:      {metrics['planar']:.16e}")


def optimise(topology: Topology) -> dict[str, object]:
    label_to_index = {label: index for index, label in enumerate(topology.labels)}
    edge_indices = np.array(
        [(label_to_index[left], label_to_index[right]) for left, right in topology.edges],
        dtype=np.int64,
    )
    face_indices = tuple(
        np.array([label_to_index[label] for label in face], dtype=np.int64)
        for face in topology.faces
    )

    positions = spectral_initial_positions(topology)
    edge_length = float(np.median(calculate_edge_lengths(positions, edge_indices)))
    face_planes = calculate_face_planes(positions, face_indices)
    variables = pack_variables(positions, edge_length, face_planes)
    stage_reports: list[dict[str, object]] = []

    for stage in STAGES:
        result = least_squares(
            residuals,
            variables,
            args=(len(topology.labels), edge_indices, face_indices, stage),
            jac="2-point",
            method="trf",
            x_scale="jac",
            ftol=1e-12,
            xtol=1e-12,
            gtol=1e-12,
            max_nfev=stage.max_evaluations,
            verbose=0,
        )
        variables = result.x
        positions, edge_length, face_planes = unpack_variables(
            variables,
            len(topology.labels),
            len(face_indices),
        )
        positions = normalise_positions(positions)
        edge_length = float(np.mean(calculate_edge_lengths(positions, edge_indices)))
        face_planes = calculate_face_planes(positions, face_indices)
        variables = pack_variables(positions, edge_length, face_planes)
        metrics = calculate_metrics(positions, edge_indices, face_indices)
        stage_reports.append(
            {
                "stage": stage.name,
                "success": bool(result.success),
                "status": int(result.status),
                "cost": float(result.cost),
                "optimality": float(result.optimality),
                "evaluations": int(result.nfev),
                "metrics": asdict(metrics),
            }
        )

    positions, edge_length, _ = unpack_variables(
        variables,
        len(topology.labels),
        len(face_indices),
    )
    metrics = calculate_metrics(positions, edge_indices, face_indices)
    return {
        "positions": positions,
        "edge_length": edge_length,
        "metrics": asdict(metrics),
        "stages": stage_reports,
        "face_count": len(topology.faces),
        "edge_count": len(topology.edges),
    }


def residuals(
    variables: np.ndarray,
    vertex_count: int,
    edge_indices: np.ndarray,
    face_indices: tuple[np.ndarray, ...],
    stage: OptimisationStage,
) -> np.ndarray:
    positions, edge_length, face_planes = unpack_variables(
        variables,
        vertex_count,
        len(face_indices),
    )
    sphere = (np.linalg.norm(positions, axis=1) - 1.0) * stage.sphere_weight
    edges = (calculate_edge_lengths(positions, edge_indices) - edge_length) * stage.edge_weight
    planar = calculate_plane_residuals(positions, face_indices, face_planes) * stage.planar_weight
    plane_norms = (np.linalg.norm(face_planes[:, :3], axis=1) - 1.0) * stage.planar_weight
    return np.concatenate((sphere, edges, planar, plane_norms))


def calculate_face_planes(
    positions: np.ndarray,
    face_indices: tuple[np.ndarray, ...],
) -> np.ndarray:
    planes = np.zeros((len(face_indices), 4), dtype=np.float64)
    for index, face in enumerate(face_indices):
        face_positions = positions[face]
        centre = np.mean(face_positions, axis=0)
        centred = face_positions - centre
        _, _, vh = np.linalg.svd(centred, full_matrices=False)
        normal = vh[-1]
        planes[index, :3] = normal
        planes[index, 3] = float(np.dot(normal, centre))
    return planes


def calculate_plane_residuals(
    positions: np.ndarray,
    face_indices: tuple[np.ndarray, ...],
    face_planes: np.ndarray,
) -> np.ndarray:
    residual_values: list[np.ndarray] = []
    for face, plane in zip(face_indices, face_planes, strict=True):
        normal = plane[:3]
        offset = plane[3]
        residual_values.append(positions[face] @ normal - offset)
    return np.concatenate(residual_values)


def pack_variables(
    positions: np.ndarray,
    edge_length: float,
    face_planes: np.ndarray,
) -> np.ndarray:
    return np.concatenate(
        (
            positions.reshape(-1),
            np.array([edge_length], dtype=np.float64),
            face_planes.reshape(-1),
        ),
    )


def unpack_variables(
    variables: np.ndarray,
    vertex_count: int,
    face_count: int,
) -> tuple[np.ndarray, float, np.ndarray]:
    positions = variables[: vertex_count * 3].reshape((vertex_count, 3))
    edge_length = float(variables[vertex_count * 3])
    plane_start = vertex_count * 3 + 1
    plane_end = plane_start + face_count * 4
    face_planes = variables[plane_start:plane_end].reshape((face_count, 4))
    return positions, edge_length, face_planes


def normalise_positions(positions: np.ndarray) -> np.ndarray:
    return positions / np.linalg.norm(positions, axis=1)[:, np.newaxis]


def write_outputs(topology: Topology, result: dict[str, object]) -> None:
    positions = result["positions"]
    if not isinstance(positions, np.ndarray):
        raise TypeError("Expected numpy positions in optimisation result.")

    vertices = {
        label: [float(component) for component in positions[index]]
        for index, label in enumerate(topology.labels)
    }
    OPTIMISED_VERTICES_PATH.write_text(
        f"{json.dumps({'vertices': vertices}, indent=2)}\n",
    )

    report = {
        "name": "Goldberg GP(2,2) optimisation report",
        "vertex_count": len(topology.labels),
        "edge_count": result["edge_count"],
        "face_count": result["face_count"],
        "edge_length": result["edge_length"],
        "target_tolerance": TARGET_TOLERANCE,
        "satisfies_target": all(
            result["metrics"][metric] <= TARGET_TOLERANCE
            for metric in ("on_sphere", "equilateral", "planar")
        ),
        "metrics": result["metrics"],
        "stages": result["stages"],
    }
    OPTIMISATION_REPORT_PATH.write_text(f"{json.dumps(report, indent=2)}\n")


if __name__ == "__main__":
    main()
