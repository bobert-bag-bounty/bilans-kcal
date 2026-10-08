"""Calibration catch_up for users without a Garmin daily total (Strava or
manual entry): summary rows exist but `kcal_total_garmin` is NULL. This used to
raise TypeError on every run (25x `calibration_error` in production for the
Strava tester, 2026-10-04 audit)."""
from datetime import time, timedelta

from app.models import CalibrationState, DailySummary, Meal, WeightLog
from app.services import calibration
from tests.test_calibration import _freeze_today, _make_db


def _seed_strava_like_days(db, n_days: int) -> None:
    for i in range(n_days):
        day = calibration.CALIBRATION_EPOCH + timedelta(days=i)
        db.add(DailySummary(user_id=1, date=day, kcal_total_garmin=None, complete=True))
        db.add(Meal(user_id=1, date=day, time=time(12, 0), kcal=1800, description="meal"))
        db.add(WeightLog(user_id=1, date=day, weight_kg=70.0))
    db.commit()


def test_catch_up_does_not_raise_without_garmin_total(tmp_path, monkeypatch):
    db = _make_db(tmp_path, "nogarmin")
    _seed_strava_like_days(db, 5)
    _freeze_today(monkeypatch, calibration.CALIBRATION_EPOCH + timedelta(days=6))

    calibration.catch_up(db, 1)

    state = db.get(CalibrationState, 1)
    assert state.factor == calibration.PRIOR_FACTOR
    assert state.days_used == 0


def test_catch_up_advances_updated_on_without_garmin_total(tmp_path, monkeypatch):
    """The cursor must move past days it cannot use, otherwise every dashboard
    visit re-scans the same range."""
    db = _make_db(tmp_path, "nogarmin_cursor")
    _seed_strava_like_days(db, 5)
    yesterday = calibration.CALIBRATION_EPOCH + timedelta(days=5)
    _freeze_today(monkeypatch, yesterday + timedelta(days=1))

    calibration.catch_up(db, 1)

    assert db.get(CalibrationState, 1).updated_on == yesterday
