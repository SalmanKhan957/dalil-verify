# Dependency Rules

- `apps/` may depend on `domains/`, `infrastructure/`, `shared/`.
- `domains/` may depend on `infrastructure/` and `shared/` only where required.
- `pipelines/` may depend on `domains/`, `infrastructure/`, and `shared/`.
- Legacy `services/` modules are compatibility wrappers during the rewrite window.
