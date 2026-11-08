"""The model card behind ``GET /model``: how the serving model was trained and how it scored.

Built once at startup from two files the training pipeline writes:

* ``meta.json`` in the artifacts folder (``model.train``): season split, the
  three models' validation scores and training times, the production pick
* ``metrics.json`` in the reports folder (``model.evaluate``): test-season
  Brier score, log loss, calibration bins, scores by game phase, sanity checks

The report is only used when it scored the same training run as the
artifacts, so the page never pairs one model with another model's numbers.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("api.modelcard")

TEST_KEYS = ("rows", "brier", "log_loss", "ece", "max_bin_gap", "calibrated_within_5pts", "final_play", "tipoff")
BIN_KEYS = ("lo", "hi", "n", "mean_pred", "frac_pos")


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as err:
        log.warning("can't read %s: %s", path, err)
        return None


def _same_run(meta: dict, report: dict) -> bool:
    if report.get("trained_at") is not None:
        return report["trained_at"] == meta.get("trained_at")
    # Reports written before trained_at was recorded: match on what both carry.
    return report.get("production") == meta.get("production") and report.get("split") == meta.get("split")


def _test_scores(result: dict) -> dict:
    out = {k: result[k] for k in TEST_KEYS if k in result}
    out["phases"] = {ph: s for ph, s in result.get("phases", {}).items() if s.get("rows")}
    out["bins"] = [{k: b.get(k) for k in BIN_KEYS} for b in result.get("bins", []) if b.get("n")]
    return out


def build_card(artifacts_dir: Path, reports_dir: Path) -> dict | None:
    """The card, or None when there's no trained model."""
    meta = _read_json(Path(artifacts_dir) / "meta.json")
    if meta is None:
        return None
    report = _read_json(Path(reports_dir) / "metrics.json")
    if report is not None and not _same_run(meta, report):
        log.warning("%s scored a different training run; leaving test results out", reports_dir / "metrics.json")
        report = None
    tested = (report or {}).get("models", {})
    names = meta.get("models") or [meta["production"]]
    return {
        "data_source": meta.get("data_source", "nba"),
        "sample": bool(meta.get("sample", False)),
        "trained_at": meta.get("trained_at"),
        "production": meta.get("production"),
        "calibrated": bool(meta.get("calibrated", False)),
        "features": meta.get("features", []),
        "split": meta.get("split"),
        "xgboost_trees": meta.get("xgboost_trees"),
        "models": {
            name: {
                "train_seconds": meta.get("train_seconds", {}).get(name),
                "val": meta.get("val", {}).get(name),
                "test": _test_scores(tested[name]) if name in tested else None,
            }
            for name in names
        },
    }
