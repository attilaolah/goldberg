# GP(2,2) Numerical Optimisation

This note describes the separate Python optimisation pipeline for finding
coordinates of the labelled GP(2,2) graph against three prioritised constraints:

- **On-sphere**: the maximum absolute difference between each vertex radius and
  the unit sphere.
- **Equilateral**: the spread between the longest and shortest graph edge.
- **Planar**: the largest best-fit-plane residual among all pentagonal and
  hexagonal faces.

The optimiser intentionally uses the existing labelled graph data as topology
input and does not modify the viewer or notation documents.

The constraints are accepted in priority order:

1. **On-sphere**: this must be as close to zero as floating-point arithmetic
   allows.
2. **Equilateral**: this is the primary optimisation target once the sphere
   constraint is effectively satisfied.
3. **Planar**: this is a secondary target and may be sacrificed when pursuing it
   would worsen the first two priorities.

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

The report includes:

- `priority_order`, which records the lexicographic acceptance order.
- `satisfies_priority_goal`, which is `true` when the on-sphere and equilateral
  metrics are below the configured target tolerance.
- `satisfies_priority_precision_goal`, which is `true` when the on-sphere and
  equilateral metrics are close to machine precision.
- `satisfies_target`, which is only `true` when all three headline metrics are
  below the configured target tolerance.

The current generated report has `satisfies_priority_goal: true` and
`satisfies_priority_precision_goal: true`, but `satisfies_target: false`. Its
headline metrics are approximately:

- on-sphere: `0.0`
- equilateral: `1.94e-16`
- planar: `3.16e-3`
