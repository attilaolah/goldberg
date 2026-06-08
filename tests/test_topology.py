from collections import Counter

from goldberg_optimisation.topology import load_topology


def test_gp_2_2_topology_counts() -> None:
    topology = load_topology()

    assert len(topology.labels) == 240
    assert len(topology.edges) == 360
    assert len(topology.faces) == 122
    assert Counter(map(len, topology.faces)) == {5: 12, 6: 110}


def test_every_edge_belongs_to_two_faces() -> None:
    topology = load_topology()
    edge_counts: Counter[tuple[str, str]] = Counter()

    for face in topology.faces:
        for index, label in enumerate(face):
            next_label = face[(index + 1) % len(face)]
            edge_counts[tuple(sorted((label, next_label)))] += 1

    assert set(edge_counts) == set(topology.edges)
    assert set(edge_counts.values()) == {2}

