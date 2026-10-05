"""Load the seed YAML files under data/ into the dict shapes the settings resolver expects.
Used by the CLI (no database) and by scripts/seed.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_countries(data_dir: Path = DATA_DIR) -> dict[str, dict[str, Any]]:
    out = {}
    for p in sorted((data_dir / "countries").glob("*.yaml")):
        d = _load(p)
        out[d["code"]] = d
    return out


def load_platforms(data_dir: Path = DATA_DIR) -> dict[str, dict[str, Any]]:
    out = {}
    for p in sorted((data_dir / "platforms").glob("*.yaml")):
        d = _load(p)
        code = d.get("platform") or p.stem
        out[code] = {
            "code": code,
            "name": d.get("name", code.title()),
            "status": d.get("status", "planned"),
            "version": int(d.get("version", 1)),
            "change_note": d.get("change_note", ""),
            "global": d.get("global", {}),
            "markets": d.get("markets", {}),
            "sources": d.get("sources", {}),
        }
    return out


def load_categories(data_dir: Path = DATA_DIR) -> dict[str, dict[str, Any]]:
    out = {}
    for p in sorted((data_dir / "categories").glob("*.yaml")):
        d = _load(p)
        out[d["code"]] = d
    return out


def load_scenarios(data_dir: Path = DATA_DIR) -> list[dict[str, Any]]:
    d = _load(data_dir / "scenarios.yaml")
    rows = []
    for s in d.get("scenarios", []):
        row = dict(s)
        row.setdefault("version", 1)
        row.setdefault("status", "published")
        rows.append(row)
    return rows


def load_weights(data_dir: Path = DATA_DIR) -> dict[str, Any]:
    d = _load(data_dir / "behavior_weights.yaml")
    return {
        "version": int(d.get("version", 1)),
        "behavior": d.get("behavior", {}),
        "score_by_goal": d.get("score_by_goal", {}),
        "change_note": d.get("change_note", ""),
    }


DEFAULT_TIERS: list[dict[str, Any]] = [
    {
        "code": "quick",
        "name": "Quick",
        "runs_target": 20,
        "min_runs": 12,
        "scenarios": 2,
        "max_audiences": 1,
        "agents": 8000,
        "archetypes": 100,
        "sort_order": 1,
    },
    {
        "code": "standard",
        "name": "Standard",
        "runs_target": 150,
        "min_runs": 60,
        "scenarios": 5,
        "max_audiences": 1,
        "agents": 20000,
        "archetypes": 200,
        "sort_order": 2,
    },
    {
        "code": "full",
        "name": "Full",
        "runs_target": 150,
        "min_runs": 60,
        "scenarios": 5,
        "max_audiences": 3,
        "agents": 20000,
        "archetypes": 200,
        "sort_order": 3,
    },
]


def tier_by_code(code: str) -> dict[str, Any]:
    for t in DEFAULT_TIERS:
        if t["code"] == code:
            return dict(t)
    return dict(DEFAULT_TIERS[1])


def load_all(data_dir: Path = DATA_DIR) -> dict[str, Any]:
    return {
        "countries": load_countries(data_dir),
        "platforms": load_platforms(data_dir),
        "categories": load_categories(data_dir),
        "scenarios": load_scenarios(data_dir),
        "weights": load_weights(data_dir),
        "tiers": {t["code"]: t for t in DEFAULT_TIERS},
    }
