import json
from dataclasses import dataclass
from pathlib import Path

import networkx as nx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH_PATH = PROJECT_ROOT / "data" / "gp_2_2_vertex_connections.json"


@dataclass(frozen=True)
class Topology:
    labels: tuple[str, ...]
    neighbours: dict[str, tuple[str, ...]]
    edges: tuple[tuple[str, str], ...]
    faces: tuple[tuple[str, ...], ...]


def load_topology(path: Path = DEFAULT_GRAPH_PATH) -> Topology:
    graph_data = json.loads(path.read_text())
    vertices = graph_data["vertices"]
    labels = tuple(vertices)
    neighbours = {
        label: tuple(vertex_data["neighbours"])
        for label, vertex_data in vertices.items()
    }
    edges = _build_edges(neighbours)
    faces = extract_faces(labels, edges)

    return Topology(labels=labels, neighbours=neighbours, edges=edges, faces=faces)


def extract_faces(
    labels: tuple[str, ...],
    edges: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, ...], ...]:
    graph = nx.Graph()
    graph.add_nodes_from(labels)
    graph.add_edges_from(edges)

    is_planar, embedding = nx.check_planarity(graph, counterexample=False)
    if not is_planar:
        raise ValueError("The GP(2,2) graph is not planar.")

    face_keys: set[tuple[str, ...]] = set()
    faces: list[tuple[str, ...]] = []
    for left, right in graph.edges:
        for start, end in ((left, right), (right, left)):
            face = tuple(embedding.traverse_face(start, end))
            key = _canonical_cycle(face)
            if key in face_keys:
                continue
            face_keys.add(key)
            faces.append(key)

    return tuple(sorted(faces, key=lambda face: (len(face), face)))


def _build_edges(neighbours: dict[str, tuple[str, ...]]) -> tuple[tuple[str, str], ...]:
    edges: set[tuple[str, str]] = set()
    for label, label_neighbours in neighbours.items():
        for neighbour in label_neighbours:
            edges.add(tuple(sorted((label, neighbour))))
    return tuple(sorted(edges))


def _canonical_cycle(cycle: tuple[str, ...]) -> tuple[str, ...]:
    forward = _minimal_rotation(cycle)
    backward = _minimal_rotation(tuple(reversed(cycle)))
    return min(forward, backward)


def _minimal_rotation(cycle: tuple[str, ...]) -> tuple[str, ...]:
    rotations = [cycle[index:] + cycle[:index] for index in range(len(cycle))]
    return min(rotations)
