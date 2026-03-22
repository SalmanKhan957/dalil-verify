from __future__ import annotations

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent / "cases"

REQUIRED_CASE_KEYS = {"id", "category", "description", "input_text", "expected"}

def _load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []

def test_case_yaml_files_exist():
    expected = {"smoke.yml", "regression_core.yml", "whitespace.yml", "adversarial.yml", "performance.yml", "api_contract.yml"}
    found = {p.name for p in ROOT.glob("*.yml")}
    missing = expected - found
    assert not missing, f"Missing case files: {sorted(missing)}"

def test_functional_case_schema():
    for name in ["smoke.yml", "regression_core.yml", "whitespace.yml", "adversarial.yml", "performance.yml"]:
        rows = _load_yaml(ROOT / name)
        assert isinstance(rows, list) and rows, f"{name} is empty or invalid"
        ids = set()
        for row in rows:
            assert REQUIRED_CASE_KEYS <= set(row.keys()), f"{name} missing required keys in {row}"
            assert row["id"] not in ids, f"Duplicate id {row['id']} in {name}"
            ids.add(row["id"])
            assert isinstance(row["expected"], dict), f"{name} expected must be a mapping in {row['id']}"

def test_api_contract_case_schema():
    rows = _load_yaml(ROOT / "api_contract.yml")
    assert isinstance(rows, list) and rows, "api_contract.yml is empty or invalid"
    ids = set()
    for row in rows:
        assert {"id", "description", "request", "expected"} <= set(row.keys()), f"Bad API contract row: {row}"
        assert row["id"] not in ids, f"Duplicate id {row['id']} in api_contract.yml"
        ids.add(row["id"])
