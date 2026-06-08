# Agent Instructions

## Domain Specification

- Load and follow `instructions/gp_2_2.md` when work involves Goldberg GP(2,2) vertex naming, patch ownership, indexing, or vertex accounting.

## Source Code Management

- Git commits should use Conventional Commit messages (for example, `feat: ...`, `fix: ...`, `docs: ...`).
- Prefer `snake_case` names for files.
- Keep code/content in files with matching extensions whenever practical (for example, HTML in `.html` files instead of embedded strings in `.js` files) so linters and security scanners can inspect the correct artifact type.
- All changed files must be formatted with Prettier (for example, `prettier -w ...`) before committing.
