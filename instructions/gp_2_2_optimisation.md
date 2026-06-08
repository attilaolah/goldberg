# GP(2,2) Numerical Optimisation

This note describes the separate Python optimisation pipeline for finding
coordinates of the labelled GP(2,2) graph that satisfy three constraints:

- **On-sphere**: the maximum absolute difference between each vertex radius and
  the unit sphere.
- **Equilateral**: the spread between the longest and shortest graph edge.
- **Planar**: the largest best-fit-plane residual among all pentagonal and
  hexagonal faces.

The optimiser intentionally uses the existing labelled graph data as topology
input and does not modify the viewer or notation documents.

Run the checks with:

```sh
uv run pytest
```

Run the optimiser with:

```sh
uv run python -m goldberg_optimisation.optimise_gp_2_2
```

The optimiser writes:

- `data/gp_2_2_optimised_vertices.json`
- `data/gp_2_2_optimisation_report.json`

The report includes `satisfies_target`, which is only `true` when the three
headline metrics are all below the configured target tolerance. A `false` value
means the run produced a useful numerical attempt, but not yet a high-accuracy
solution of the three constraints.

The current generated report has `satisfies_target: false`. Its headline
metrics are approximately:

- on-sphere: `2.22e-16`
- equilateral: `1.53e-3`
- planar: `3.01e-3`
