"""Versioned scenario files: one learner model, one behaviour model, one design, fixed seeds."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

SCHEMA = "sim-scenario/1"
SCENARIO_DIR = Path(__file__).parent / "scenarios"

DEFAULT_BEHAVIOUR = {
    "answer_rate": 0.90,             # share of day-7 checks answered when nothing else interferes
    "answer_delay_days": [7, 10],    # continuous U(a, b) after completion
    "late_rate": 0.0,                # share answered after the window instead
    "late_delay_days": [15, 20],
    "mnar_slope": 0.0,               # extra skip probability per unit of expected failure (1 - p)
    "arm_skip": {"baseline": 0.0, "variant": 0.0},
    "outside_study_rate": {"baseline": 0.0, "variant": 0.0},
    "outside_declared_share": 1.0,   # declared outside study is excluded; undeclared silently helps
    "outside_boost_logit": 1.0,
    "false_negative_rate": {"baseline": 0.0, "variant": 0.0},  # correct answers the key rejects
    "missed_day_rate": 0.0,
    "dropout_hazard": 0.0,           # per active day
    "frustration_hazard": 0.0,       # added per day × share of the last 3 checks failed
}
DEFAULT_DESIGN = {"units_per_day": 3, "contrast": "order-v1"}
MODEL_KINDS = ("bernoulli", "half-life", "log-delay")
LATENT_KEYS = {"kind", "intercept_logit", "ability_sd", "difficulty_sd", "concept_size", "concept_sd",
               "method_logit_mean", "method_logit_sd", "reversed_share", "drift_logit_per_unit",
               "novelty_logit", "novelty_half_life_units", "arm_difficulty_shift"}
MODEL_KEYS = {
    "bernoulli": {"kind", "baseline", "gap_points"},
    "half-life": LATENT_KEYS | {"half_life_days", "variant_half_life_ratio"},
    "log-delay": LATENT_KEYS | {"decay"},
}


class ScenarioError(ValueError):
    pass


def _merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key not in merged:
            raise ScenarioError(f"unknown field {key!r}")
        merged[key] = _merge(merged[key], value) if isinstance(merged[key], dict) else value
    return merged


def normalize(raw: dict) -> dict:
    """Validate a scenario and fill defaults; the result is what gets hashed and run."""
    if raw.get("schema") != SCHEMA:
        raise ScenarioError(f"schema must be {SCHEMA}")
    for key in ("id", "model", "learners"):
        if key not in raw:
            raise ScenarioError(f"{key} is required")
    unknown = set(raw) - {"schema", "id", "description", "model", "behaviour", "design", "learners", "truth_gap_note"}
    if unknown:
        raise ScenarioError(f"unknown fields {sorted(unknown)}")
    model = dict(raw["model"])
    if model.get("kind") not in MODEL_KINDS:
        raise ScenarioError(f"model.kind must be one of {MODEL_KINDS}")
    unknown_model = set(model) - MODEL_KEYS[model["kind"]]
    if unknown_model:
        # A misspelt option would otherwise be hashed and silently ignored.
        raise ScenarioError(f"unknown {model['kind']} model fields {sorted(unknown_model)}")
    learners = raw["learners"]
    if set(learners) - {"seeds", "per_seed"}:
        raise ScenarioError(f"unknown learners fields {sorted(set(learners) - {'seeds', 'per_seed'})}")
    if not learners.get("seeds") or int(learners.get("per_seed", 0)) < 1:
        raise ScenarioError("learners need seeds and per_seed >= 1")
    scenario = {
        "schema": SCHEMA, "id": str(raw["id"]), "description": raw.get("description", ""),
        "model": model,
        "behaviour": _merge(DEFAULT_BEHAVIOUR, raw.get("behaviour", {})),
        "design": _merge(DEFAULT_DESIGN, raw.get("design", {})),
        "learners": {"seeds": [int(s) for s in learners["seeds"]], "per_seed": int(learners["per_seed"])},
    }
    if scenario["design"]["units_per_day"] < 1:
        raise ScenarioError("units_per_day must be positive")
    return scenario


def expand(raw: dict) -> list[dict]:
    """A file is one scenario, or a suite whose "rows" override model/behaviour/design per row."""
    rows = raw.get("rows")
    if not rows:
        return [normalize(raw)]
    base = {k: v for k, v in raw.items() if k != "rows"}
    expanded = []
    for row in rows:
        merged = copy.deepcopy(base)
        merged["id"] = f"{raw['id']}/{row['id']}"
        for section in ("model", "behaviour", "design"):
            if section in row:
                # A row's per-arm dicts replace the suite's; normalize() refills missing arms from defaults.
                inherited = merged.get(section, {})
                kind = row[section].get("kind")
                old = inherited.get("kind")
                if section == "model" and kind in MODEL_KEYS and old in MODEL_KEYS and kind != old:
                    # Switching kind drops only valid fields of the old kind that the new kind does not use;
                    # anything unknown to both survives the merge and fails validation.
                    inherited = {k: v for k, v in inherited.items()
                                 if k in MODEL_KEYS[kind] or k not in MODEL_KEYS[old]}
                merged[section] = {**inherited, **row[section]}
        expanded.append(normalize(merged))
    return expanded


def scenario_hash(scenario: dict) -> str:
    return hashlib.sha256(json.dumps(scenario, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def load(name_or_path: str | Path) -> list[dict]:
    """All rows of a scenario file, by name (in scenarios/) or path."""
    path = Path(name_or_path)
    if not path.suffix:
        path = SCENARIO_DIR / f"{name_or_path}.json"
    return expand(json.loads(path.read_text(encoding="utf-8")))


def available() -> list[str]:
    return sorted(p.stem for p in SCENARIO_DIR.glob("*.json"))
