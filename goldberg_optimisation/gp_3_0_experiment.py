import json
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import least_squares

from goldberg_optimisation.metrics import calculate_face_planarity_error
from goldberg_optimisation.topology import PROJECT_ROOT


OUTPUT_PATH = PROJECT_ROOT / "data" / "gp_3_0_experiment.json"
INITIAL_VARIABLES = np.array([np.sqrt(3.0) / 2.0, 1.0, 2.0, 1.0, 1.0, 1.0])
TARGET_TOLERANCE = 1e-12


@dataclass(frozen=True)
class GP30Metrics:
    on_sphere: float
    equilateral: float
    planar: float
    shortest_edge: float
    longest_edge: float


@dataclass(frozen=True)
class ConstraintVariant:
    name: str
    description: str
    radius_mode: str


VARIANTS = (
    ConstraintVariant(
        "strict_unit_sphere",
        "Planarity, single edge length, and all three independent shell radii fixed to 1.",
        "all",
    ),
    ConstraintVariant(
        "paper_commented_pnas_case",
        "Planarity, single edge length, and only R0(1) fixed to 1, matching the commented PNAS-case line in GP30.m.",
        "first",
    ),
)


def main() -> None:
    results = [run_variant(variant) for variant in VARIANTS]
    output = {
        "name": "Goldberg GP(3,0) experiment",
        "source": "Python translation of the supplementary GP30.m constraints.",
        "target_tolerance": TARGET_TOLERANCE,
        "initial_variables": INITIAL_VARIABLES.tolist(),
        "results": results,
    }
    OUTPUT_PATH.write_text(f"{json.dumps(output, indent=2)}\n")

    for result in results:
        metrics = result["metrics"]
        print(
            f"{result['name']}: exact={result['exact']} "
            f"on_sphere={metrics['on_sphere']:.3e} "
            f"equilateral={metrics['equilateral']:.3e} "
            f"planar={metrics['planar']:.3e}",
        )


def run_variant(variant: ConstraintVariant) -> dict[str, object]:
    result = least_squares(
        variant_residuals,
        INITIAL_VARIABLES,
        args=(variant,),
        jac="3-point",
        method="trf",
        x_scale="jac",
        ftol=1e-15,
        xtol=1e-15,
        gtol=1e-15,
        max_nfev=10000,
    )
    metrics = calculate_gp30_metrics(result.x)
    worst_error = max(metrics.on_sphere, metrics.equilateral, metrics.planar)
    return {
        "name": variant.name,
        "description": variant.description,
        "exact": worst_error <= TARGET_TOLERANCE,
        "variables": [float(value) for value in result.x],
        "solver": {
            "success": bool(result.success),
            "status": int(result.status),
            "cost": float(result.cost),
            "optimality": float(result.optimality),
            "evaluations": int(result.nfev),
        },
        "metrics": asdict(metrics),
        "worst_error": worst_error,
    }


def variant_residuals(variables: np.ndarray, variant: ConstraintVariant) -> np.ndarray:
    lengths, planarity, _ = calculate_gp30_parts(variables)
    edge_residuals = lengths - np.mean(lengths)
    if variant.radius_mode == "all":
        radius_residuals = variables[3:6] - 1.0
    elif variant.radius_mode == "first":
        radius_residuals = np.array([variables[3] - 1.0])
    else:
        raise ValueError(f"Unknown radius mode: {variant.radius_mode}")
    return np.concatenate((planarity, edge_residuals, radius_residuals))


def calculate_gp30_metrics(variables: np.ndarray) -> GP30Metrics:
    lengths, planarity, radii = calculate_gp30_parts(variables)
    return GP30Metrics(
        on_sphere=float(np.max(np.abs(radii - 1.0))),
        equilateral=float(np.max(lengths) - np.min(lengths)),
        planar=float(np.max(planarity)),
        shortest_edge=float(np.min(lengths)),
        longest_edge=float(np.max(lengths)),
    )


def calculate_gp30_parts(variables: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    face_1_points, face_2_points = calculate_gp30_points(variables)
    lengths = np.array(
        [
            np.linalg.norm(face_1_points[2] - face_2_points[2]),
            np.linalg.norm(face_1_points[1] - face_1_points[2]),
            np.linalg.norm(face_1_points[1] - face_1_points[3]),
            np.linalg.norm(face_1_points[3] - face_2_points[0]),
        ],
        dtype=np.float64,
    )
    face_1 = np.array(
        [
            face_1_points[0],
            face_1_points[1],
            face_1_points[4],
            face_1_points[6],
            face_1_points[3],
            face_1_points[5],
        ],
    )
    face_2 = np.array(
        [
            face_1_points[1],
            face_1_points[2],
            face_1_points[3],
            face_2_points[0],
            face_2_points[1],
            face_2_points[2],
        ],
    )
    planarity = np.array(
        [
            calculate_face_planarity_error(face_1),
            calculate_face_planarity_error(face_2),
        ],
        dtype=np.float64,
    )
    radii = np.linalg.norm(np.vstack((face_1_points, face_2_points)), axis=1)
    return lengths, planarity, radii


def calculate_gp30_points(variables: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    aa = np.sqrt(3.0) / 2.0
    p1 = np.array([variables[0], variables[0] / aa / 2.0])
    p2 = np.array([0.0, variables[1]])
    p3 = np.array([0.0, variables[2]])
    p0 = np.column_stack((np.vstack((p1, p2, p3)), np.ones(3)))
    radii = variables[3:6]

    source_triangle = calculate_source_triangle()
    target_1, target_2 = calculate_icosahedron_targets()
    triangle_map_1 = target_1 @ np.linalg.inv(source_triangle)
    triangle_map_2 = target_2 @ np.linalg.inv(source_triangle)

    x1 = p0[0, 0]
    y1 = p0[0, 1]
    y2 = p0[1, 1]
    mirrored_points = np.array(
        [
            [-x1, y1, 1.0],
            [x1, -y1, 1.0],
            [-np.sqrt(3.0) * y2 / 2.0, -y2 / 2.0, 1.0],
            [0.0, -y2, 1.0],
        ],
    )
    planar_points = np.vstack((p0, mirrored_points))
    face_1 = triangle_map_1 @ planar_points.T
    face_2 = triangle_map_2 @ planar_points.T

    radius_pattern = np.array([radii[0], radii[1], radii[2], radii[0], radii[0], radii[1], radii[1]])
    face_1 = face_1 * (radius_pattern / np.sqrt(np.sum(face_1 * face_1, axis=0)))
    face_2 = face_2 * (radius_pattern / np.sqrt(np.sum(face_2 * face_2, axis=0)))
    return face_1.T, face_2.T


def calculate_source_triangle() -> np.ndarray:
    m = 3.0
    n = 0.0
    triangle_edge = np.sqrt((m * np.sqrt(3.0) + n * np.sqrt(3.0) / 2.0) ** 2 + (n * 1.5) ** 2)
    triangle_radius = triangle_edge / np.sqrt(3.0)
    point_a = np.array([0.0, triangle_radius, 1.0])
    point_b = np.array([triangle_radius * np.sqrt(3.0) / 2.0, -triangle_radius / 2.0, 1.0])
    point_c = np.array([-triangle_radius * np.sqrt(3.0) / 2.0, -triangle_radius / 2.0, 1.0])
    return np.column_stack((point_a, point_b, point_c))


def calculate_icosahedron_targets() -> tuple[np.ndarray, np.ndarray]:
    edge_length = 1.0 / np.sin(2.0 * np.pi / 5.0)
    y = -edge_length / 2.0 / np.tan(np.deg2rad(36.0))
    z = np.sqrt(1.0 - (edge_length / 2.0) ** 2 - y * y)
    point_a = np.array([0.0, 0.0, 1.0])
    point_b = np.array([edge_length / 2.0, y, z])
    point_c = np.array([-edge_length / 2.0, y, z])
    point_d = np.array(
        [
            -np.cos(np.deg2rad(18.0)) * edge_length / 2.0 / np.sin(np.deg2rad(36.0)),
            np.sin(np.deg2rad(72.0)) * edge_length - edge_length / 2.0 / np.tan(np.deg2rad(36.0)),
            z,
        ],
    )
    return np.column_stack((point_a, point_b, point_c)), np.column_stack((point_a, point_c, point_d))


if __name__ == "__main__":
    main()

