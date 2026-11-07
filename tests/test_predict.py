"""predict(state) behaves sensibly for every trained model (skips without artifacts)."""

import pytest

from model.predict import MODEL_NAMES, WinProbModel, load_meta, state_vector
from pipeline import config
from pipeline.features import FEATURES


def models():
    if not (config.ARTIFACTS_DIR / "meta.json").exists():
        pytest.skip("no trained model yet")
    meta = load_meta()
    return [WinProbModel(n, config.ARTIFACTS_DIR) for n in meta["models"]]


def test_state_vector_fills_margin_x_time():
    v = state_vector({"margin": 8, "seconds_left": 99})
    assert len(v) == len(FEATURES)
    assert v[FEATURES.index("margin_x_time")] == pytest.approx(0.8)
    assert v[FEATURES.index("home_possession")] == 0.5


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_model_sanity(name):
    by_name = {m.name: m for m in models()}
    if name not in by_name:
        pytest.skip(f"{name} not trained")
    m = by_name[name]
    late_lead = m.predict({"margin": 8, "seconds_left": 120})
    half_lead = m.predict({"margin": 8, "seconds_left": 1440})
    tied = m.predict({"margin": 0, "seconds_left": 2880})
    over = m.predict({"margin": 3, "seconds_left": 0})
    assert 0 < tied < 1
    # The PRD's motivating example: up 8 with 2 minutes left is safer than up 8 at the half.
    assert late_lead > half_lead > 0.5
    assert over > 0.97
    assert m.predict({"margin": 0, "seconds_left": 2880, "strength_gap": 8}) > tied


def test_isotonic_calibration_applies(tmp_path, bundle):
    import shutil

    import numpy as np

    from model.train import fit_isotonic

    for f in bundle["artifacts"].iterdir():
        shutil.copy(f, tmp_path / f.name)
    raw = WinProbModel("logreg", tmp_path)
    p = np.linspace(0.01, 0.99, 200)
    y = (np.random.default_rng(0).random(200) < p**2).astype(float)  # truth is p^2: raw is overconfident
    xs, ys = fit_isotonic(p, y)
    assert np.all(np.diff(ys) >= 0), "calibration map must be monotone"
    np.savez(tmp_path / "logreg_calibration.npz", x=xs, y=ys)
    cal = WinProbModel("logreg", tmp_path)
    assert cal.calibrated and not raw.calibrated
    state = {"margin": 0, "seconds_left": 2880}
    assert cal.predict(state) == pytest.approx(float(np.interp(raw.predict(state), xs, ys)), abs=1e-9)
