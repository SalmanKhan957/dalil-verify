from __future__ import annotations

import ast
from pathlib import Path

RUNTIME_ROOTS = ("apps", "domains", "pipelines")
FORBIDDEN_PREFIXES = ("services", "scripts")

def _iter_python_files(root: Path):
    for runtime_root in RUNTIME_ROOTS:
        yield from (root / runtime_root).rglob("*.py")

def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules

def test_runtime_layers_do_not_import_legacy_services_or_scripts() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    violations: list[str] = []
    for path in _iter_python_files(repo_root):
        for module in _imported_modules(path):
            if module.startswith(FORBIDDEN_PREFIXES):
                violations.append(f"{path.relative_to(repo_root)} -> {module}")
    assert violations == [], "\n".join(violations)
