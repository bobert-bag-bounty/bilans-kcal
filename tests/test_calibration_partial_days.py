"""Partially logged days in calibration (2026-10-04 audit): a day with only
breakfast logged looks like a huge deficit and pushed the factor down by the
full daily step; 20% such days drifted it towards the clamp."""
import random
from datetime import time, timedelta

from sqlalchemy import select

from app.models import CalibrationLog, DailySummary, Meal, UsageDaily, WeightLog
from app.services import calibration
from tests.test_calibration import (
    GARMIN_KCAL_OUT, KCAL_IN, TRUE_FACTOR, _freeze_today, _make_db, _true_weight,
)

PARTIAL_KCAL = 500          # breakfast only: 0.2 of expenditure


def _seed(db, n_days, partial_every=None, seed=42):
    rng = random.Random(seed)
    for i in range(n_days):
        day = calibration.CALIBRATION_EPOCH + timedelta(days=i)
        partial = partial_every is not None and i % partial_every == partial_every - 1
        db.add(DailySummary(user_id=1, date=day, kcal_total_garmin=GARMIN_KCAL_OUT,
                            steps=9000, complete=True))
        db.add(Meal(user_id=1, date=day, time=time(8, 0),
                    kcal=PARTIAL_KCAL if partial else KCAL_IN, description="meal"))
        db.add(WeightLog(user_id=1, date=day,
                         weight_kg=round(_true_weight(i) + rng.uniform(-0.5, 0.5), 2)))
    db.commit()


def test_partial_day_is_skipped_and_counted(tmp_path, monkeypatch):
    db = _make_db(tmp_path, "partial")
    _seed(db, 10, partial_every=5)                       # days 4 and 9 partial
    _freeze_today(monkeypatch, calibration.CALIBRATION_EPOCH + timedelta(days=10))

    calibration.catch_up(db, 1)

    logged = {r.day for r in db.scalars(select(CalibrationLog)).all()}
    partial_days = {calibration.CALIBRATION_EPOCH + timedelta(days=i) for i in (4, 9)}
    assert not logged & partial_days
    skips = db.scalars(select(UsageDaily).where(UsageDaily.event == "calibration_skip_partial")).all()
    assert sum(r.count for r in skips) == 2


def test_partial_days_do_not_drag_the_factor_down(tmp_path, monkeypatch):
    clean = _make_db(tmp_path, "clean")
    _seed(clean, 60)
    noisy = _make_db(tmp_path, "noisy")
    _seed(noisy, 60, partial_every=5)                    # 20% partial days
    _freeze_today(monkeypatch, calibration.CALIBRATION_EPOCH + timedelta(days=60))

    calibration.catch_up(clean, 1)
    calibration.catch_up(noisy, 1)

    f_clean = calibration.current_factor(clean, 1)
    f_noisy = calibration.current_factor(noisy, 1)
    assert abs(f_noisy - f_clean) < 0.02
    assert abs(f_noisy - TRUE_FACTOR) < abs(calibration.CLAMP_LOW - TRUE_FACTOR)


def test_plausibility_threshold():
    assert calibration._plausible_intake(0.48 * 4361, 4361)    # real big training day
    assert not calibration._plausible_intake(500, 2500)


def test_batch_compute_ignores_partial_days(tmp_path, monkeypatch):
    db = _make_db(tmp_path, "batch")
    _seed(db, 14, partial_every=2)                       # 7 of 14 partial
    _freeze_today(monkeypatch, calibration.CALIBRATION_EPOCH + timedelta(days=14))

    # 7 plausible days < MIN_VALID_DAYS_BATCH -> no snapshot instead of a skewed one
    assert calibration.compute(db, 1) is None
