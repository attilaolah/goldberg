import json
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import least_squares, minimize

from goldberg_optimisation.initial_positions import spectral_initial_positions
from goldberg_optimisation.metrics import calculate_edge_lengths, calculate_metrics
from goldberg_optimisation.topology import PROJECT_ROOT, Topology, load_topology


OPTIMISED_VERTICES_PATH = PROJECT_ROOT / "data" / "gp_2_2_optimised_vertices.json"
OPTIMISATION_REPORT_PATH = PROJECT_ROOT / "data" / "gp_2_2_optimisation_report.json"
TARGET_TOLERANCE = 1e-12
PRIORITY_PRECISION_TOLERANCE = 5e-16
TARGET_METRICS = ("on_sphere", "equilateral", "planar")
PRIORITY_METRICS = TARGET_METRICS
PLANARITY_POLISH_ITERATIONS = 13
PLANARITY_REPAIR_PASSES = 4


@dataclass(frozen=True)
class OptimisationStage:
    name: str
    sphere_weight: float
    edge_weight: float
    planar_weight: float
    max_evaluations: int


STAGES = (
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

    positions, edge_length, sphere_edge_report = optimise_sphere_and_edges(
        spectral_initial_positions(topology),
        edge_indices,
        face_indices,
    )
    face_planes = calculate_face_planes(positions, face_indices)
    variables = pack_variables(positions, edge_length, face_planes)
    stage_reports: list[dict[str, object]] = [sphere_edge_report]
    candidates: list[dict[str, object]] = [
        {
            "stage": sphere_edge_report["stage"],
            "positions": positions.copy(),
            "edge_length": edge_length,
            "metrics": sphere_edge_report["metrics"],
            "satisfied_target_count": sphere_edge_report["satisfied_target_count"],
        },
    ]

    polished_positions, polished_edge_length, polished_report = optimise_planarity_with_priority_constraints(
        positions,
        edge_indices,
        face_indices,
    )
    stage_reports.append(polished_report)
    candidates.append(
        {
            "stage": polished_report["stage"],
            "positions": polished_positions.copy(),
            "edge_length": polished_edge_length,
            "metrics": polished_report["metrics"],
            "satisfied_target_count": polished_report["satisfied_target_count"],
        }
    )

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
        satisfied_target_count = count_satisfied_targets(asdict(metrics))
        stage_reports.append(
            {
                "stage": stage.name,
                "success": bool(result.success),
                "status": int(result.status),
                "cost": float(result.cost),
                "optimality": float(result.optimality),
                "evaluations": int(result.nfev),
                "satisfied_target_count": satisfied_target_count,
                "metrics": asdict(metrics),
            }
        )
        candidates.append(
            {
                "stage": stage.name,
                "positions": positions.copy(),
                "edge_length": edge_length,
                "metrics": asdict(metrics),
                "satisfied_target_count": satisfied_target_count,
            }
        )

    selected = select_best_candidate(candidates)
    return {
        "positions": selected["positions"],
        "edge_length": selected["edge_length"],
        "metrics": selected["metrics"],
        "selected_stage": selected["stage"],
        "satisfied_target_count": selected["satisfied_target_count"],
        "stages": stage_reports,
        "face_count": len(topology.faces),
        "edge_count": len(topology.edges),
    }


def optimise_sphere_and_edges(
    positions: np.ndarray,
    edge_indices: np.ndarray,
    face_indices: tuple[np.ndarray, ...],
) -> tuple[np.ndarray, float, dict[str, object]]:
    edge_length = float(np.mean(calculate_edge_lengths(positions, edge_indices)))
    result = least_squares(
        sphere_edge_residuals,
        pack_sphere_edge_variables(positions, edge_length),
        args=(len(positions), edge_indices),
        jac="3-point",
        method="trf",
        x_scale="jac",
        ftol=1e-15,
        xtol=1e-15,
        gtol=1e-15,
        max_nfev=1000,
        verbose=0,
    )
    positions, edge_length = unpack_sphere_edge_variables(result.x, len(positions))
    positions = normalise_positions(positions)
    edge_length = float(np.mean(calculate_edge_lengths(positions, edge_indices)))
    metrics = calculate_metrics(positions, edge_indices, face_indices)
    report = {
        "stage": "sphere_and_edges_refine",
        "success": bool(result.success),
        "status": int(result.status),
        "cost": float(result.cost),
        "optimality": float(result.optimality),
        "evaluations": int(result.nfev),
        "satisfied_target_count": count_satisfied_targets(asdict(metrics)),
        "metrics": asdict(metrics),
    }
    return positions, edge_length, report


def optimise_planarity_with_priority_constraints(
    positions: np.ndarray,
    edge_indices: np.ndarray,
    face_indices: tuple[np.ndarray, ...],
) -> tuple[np.ndarray, float, dict[str, object]]:
    result = minimize(
        planarity_objective,
        positions.reshape(-1),
        args=(len(positions), face_indices),
        method="SLSQP",
        constraints=[
            {
                "type": "eq",
                "fun": sphere_constraint,
                "args": (len(positions),),
            },
            {
                "type": "eq",
                "fun": squared_edge_constraint,
                "args": (len(positions), edge_indices),
            },
        ],
        options={
            "disp": False,
            "ftol": 1e-14,
            "maxiter": PLANARITY_POLISH_ITERATIONS,
        },
    )
    repaired_positions = result.x.reshape((len(positions), 3))
    repaired_edge_length = float(np.mean(calculate_edge_lengths(repaired_positions, edge_indices)))
    repair_evaluations = 0
    repair_success = True
    for _ in range(PLANARITY_REPAIR_PASSES):
        repaired_positions, repaired_edge_length, repair_report = optimise_sphere_and_edges(
            repaired_positions,
            edge_indices,
            face_indices,
        )
        repair_evaluations += int(repair_report["evaluations"])
        repair_success = repair_success and bool(repair_report["success"])

    metrics = calculate_metrics(repaired_positions, edge_indices, face_indices)
    report = {
        "stage": "planarity_bounded_polish",
        "success": bool(repair_success),
        "status": int(result.status),
        "cost": float(result.fun),
        "optimality": None,
        "evaluations": int(result.nfev),
        "repair_evaluations": repair_evaluations,
        "satisfied_target_count": count_satisfied_targets(asdict(metrics)),
        "metrics": asdict(metrics),
    }
    return repaired_positions, repaired_edge_length, report


def planarity_objective(
    variables: np.ndarray,
    vertex_count: int,
    face_indices: tuple[np.ndarray, ...],
) -> float:
    residual_values = calculate_planarity_residuals(variables.reshape((vertex_count, 3)), face_indices)
    return float(np.dot(residual_values, residual_values))


def calculate_planarity_residuals(
    positions: np.ndarray,
    face_indices: tuple[np.ndarray, ...],
) -> np.ndarray:
    residual_values: list[np.ndarray] = []
    for face in face_indices:
        face_positions = positions[face]
        centre = np.mean(face_positions, axis=0)
        centred = face_positions - centre
        _, _, vh = np.linalg.svd(centred, full_matrices=False)
        residual_values.append(centred @ vh[-1])
    return np.concatenate(residual_values)


def sphere_constraint(variables: np.ndarray, vertex_count: int) -> np.ndarray:
    positions = variables.reshape((vertex_count, 3))
    return np.sum(positions * positions, axis=1) - 1.0


def squared_edge_constraint(
    variables: np.ndarray,
    vertex_count: int,
    edge_indices: np.ndarray,
) -> np.ndarray:
    positions = variables.reshape((vertex_count, 3))
    edge_deltas = positions[edge_indices[:, 0]] - positions[edge_indices[:, 1]]
    squared_lengths = np.sum(edge_deltas * edge_deltas, axis=1)
    return squared_lengths[1:] - squared_lengths[0]


def sphere_edge_residuals(
    variables: np.ndarray,
    vertex_count: int,
    edge_indices: np.ndarray,
) -> np.ndarray:
    positions, edge_length = unpack_sphere_edge_variables(variables, vertex_count)
    sphere = np.linalg.norm(positions, axis=1) - 1.0
    edges = calculate_edge_lengths(positions, edge_indices) - edge_length
    return np.concatenate((sphere, edges))


def pack_sphere_edge_variables(positions: np.ndarray, edge_length: float) -> np.ndarray:
    return np.concatenate((positions.reshape(-1), np.array([edge_length], dtype=np.float64)))


def unpack_sphere_edge_variables(
    variables: np.ndarray,
    vertex_count: int,
) -> tuple[np.ndarray, float]:
    positions = variables[: vertex_count * 3].reshape((vertex_count, 3))
    edge_length = float(variables[vertex_count * 3])
    return positions, edge_length


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


def count_satisfied_targets(metrics: dict[str, float]) -> int:
    return sum(metrics[metric] <= TARGET_TOLERANCE for metric in TARGET_METRICS)


def select_best_candidate(candidates: list[dict[str, object]]) -> dict[str, object]:
    return min(
        candidates,
        key=priority_key,
    )


def priority_key(candidate: dict[str, object]) -> tuple[int, float, float]:
    metrics = candidate["metrics"]
    on_sphere = float(metrics["on_sphere"])
    equilateral = float(metrics["equilateral"])
    planar = float(metrics["planar"])
    if on_sphere > PRIORITY_PRECISION_TOLERANCE:
        return (2, on_sphere, equilateral)
    if equilateral > PRIORITY_PRECISION_TOLERANCE:
        return (1, equilateral, planar)
    return (0, equilateral, planar)


def satisfies_priority_goal(metrics: dict[str, float]) -> bool:
    return all(metrics[metric] <= TARGET_TOLERANCE for metric in ("on_sphere", "equilateral"))


def satisfies_priority_precision_goal(metrics: dict[str, float]) -> bool:
    return all(metrics[metric] <= PRIORITY_PRECISION_TOLERANCE for metric in ("on_sphere", "equilateral"))


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
        "selected_stage": result["selected_stage"],
        "priority_order": list(PRIORITY_METRICS),
        "target_tolerance": TARGET_TOLERANCE,
        "priority_precision_tolerance": PRIORITY_PRECISION_TOLERANCE,
        "satisfied_target_count": result["satisfied_target_count"],
        "satisfies_priority_goal": satisfies_priority_goal(result["metrics"]),
        "satisfies_priority_precision_goal": satisfies_priority_precision_goal(result["metrics"]),
        "satisfies_target": all(
            result["metrics"][metric] <= TARGET_TOLERANCE
            for metric in TARGET_METRICS
        ),
        "metrics": result["metrics"],
        "stages": result["stages"],
    }
    OPTIMISATION_REPORT_PATH.write_text(f"{json.dumps(report, indent=2)}\n")


if __name__ == "__main__":
    main()
