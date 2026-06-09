# GP(2,2) Local Patch Experiment

This experiment grows a rendered patch outward from the `N` pentagon and
optimises only the vertices and faces in that selected patch.

To avoid the trivial collapsed solution where all selected edges have length
zero, each selected face edge is fitted to the current global priority edge
length from `data/gp_2_2_optimisation_report.json`.

Run it with:

```sh
uv run python -m goldberg_optimisation.local_patch_experiment
```

The experiment writes:

- `data/gp_2_2_local_patch_experiment.json`

Current results with an exactness threshold of `1e-12`:

- The pentagon alone is exact.
- The pentagon plus one neighbouring hexagon is exact.
- The pentagon plus two adjacent neighbouring hexagons is not exact.
- The full ring of five hexagons around the pentagon is not exact.
- Adding one more outer face to the full ring is not exact.
