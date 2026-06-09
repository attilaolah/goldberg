# GP(3,0) Numerical Experiment

This experiment is a Python translation of the supplementary `GP30.m` MATLAB
function from the Goldberg geometry paper.

It currently checks two variants:

- **`strict_unit_sphere`**: planarity, single edge length, and all three
  independent shell radii fixed to `1`.
- **`paper_commented_pnas_case`**: planarity, single edge length, and only
  `R0(1)` fixed to `1`, matching the commented PNAS-case line in `GP30.m`.

Run it with:

```sh
uv run python -m goldberg_optimisation.gp_3_0_experiment
```

The experiment writes:

- `data/gp_3_0_experiment.json`

Current results do not verify all three constraints at machine precision:

- `strict_unit_sphere`: all vertices are close to the unit sphere, but the
  single-edge and planarity residuals remain around `1e-3`.
- `paper_commented_pnas_case`: edge equality and planarity become very small,
  but the independent radii are not all on the unit sphere.
