"""Usual workout in the day forecast (2026-10-04 audit: the morning target
missed every training day by the whole workout, median forecast/actual 0.65)."""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Activity, DailySummary, User
from app.services import usage
from app.services.energy import WAKING_END_H, WAKING_START_H, full_day_forecast
from tests.conftest import app_today
from tests.test_activities_api import _seed_summary, _user_id, clients  # noqa: F401

WAKING = WAKING_END_H - WAKING_START_H


def test_workout_not_done_yet_is_expected_for_the_rest_of_the_day():
    f = full_day_forecast(measured=800, bmr_full=2000, baseline_neat=200, hour_local=9.0,
                          baseline_activity=1000)
    assert f.activity_left == pytest.approx(1000 * (WAKING_END_H - 9) / WAKING)
    assert f.total == pytest.approx(f.measured + f.resting_left + f.neat_left + f.activity_left)


def test_workout_already_done_adds_nothing():
    f = full_day_forecast(1900, 2000, 200, 12.0, baseline_activity=1000, activity_done=1100)
    assert f.activity_left == 0


def test_partial_workout_leaves_the_rest():
    f = full_day_forecast(1500, 2000, 200, 6.0, baseline_activity=1000, activity_done=400)
    assert f.activity_left == pytest.approx(600)


def test_nothing_expected_after_the_waking_window():
    f = full_day_forecast(3000, 2000, 200, 23.5, baseline_activity=1000)
    assert f.activity_left == 0
    assert full_day_forecast(3000, 2000, 200, 24.0, baseline_activity=1000).total == 3000


def test_defaults_keep_the_previous_formula():
    f = full_day_forecast(811, 1752, 400, 9.0)
    assert f.activity_left == 0 and f.baseline_activity == 0


def _seed_training_week(SessionLocal, user_id, today, ride_kcal):
    db = SessionLocal()
    for i, kcal in enumerate(ride_kcal, start=1):
        d = today - timedelta(days=i)
        active = 300 + max(kcal - 75, 0)       # NEAT 300 + the ride's net kcal
        db.add(DailySummary(user_id=user_id, date=d, kcal_total_garmin=1800 + active,
                            kcal_active_garmin=active, kcal_bmr_garmin=1800,
                            steps=6000, complete=True))
        if kcal:
            db.add(Activity(user_id=user_id, date=d, type="cycling", duration_s=3600,
                            distance_m=30000, kcal_garmin=kcal, kcal_bmr_garmin=75,
                            garmin_id=f"ride-{i}", source="garmin"))
    db.commit()
    db.close()


def test_api_forecast_includes_usual_workout(clients):  # noqa: F811
    alice, _, SessionLocal = clients
    today = app_today()
    user_id = _user_id(SessionLocal, "alice@example.com")
    # rides on 5 of 7 days, net 1000 kcal each -> median 1000
    _seed_training_week(SessionLocal, user_id, today, [1075, 1075, 0, 1075, 1075, 0, 1075])
    _seed_summary(SessionLocal, user_id, today, kcal_total_garmin=811, kcal_active_garmin=60,
                  kcal_bmr_garmin=751, steps=1200, complete=False,
                  sync_ts=datetime(today.year, today.month, today.day, 7, 0))

    body = alice.get(f"/api/day/{today.isoformat()}").json()
    f = body["forecast"]

    assert f["baseline_activity"] == 1000
    assert f["activity_left"] > 700                 # 08:00/09:00 local, nothing done yet
    assert f["baseline_neat"] == 300
    assert abs(body["forecast_kcal"] - (f["measured"] + f["resting_left"] + f["neat_left"]
                                        + f["activity_left"])) <= 2


def test_api_forecast_ignores_workouts_of_an_occasional_trainer(clients):  # noqa: F811
    alice, _, SessionLocal = clients
    today = app_today()
    user_id = _user_id(SessionLocal, "alice@example.com")
    _seed_training_week(SessionLocal, user_id, today, [1075, 0, 0, 1075, 0, 0, 1075])
    _seed_summary(SessionLocal, user_id, today, kcal_total_garmin=811, kcal_active_garmin=60,
                  kcal_bmr_garmin=751, steps=1200, complete=False,
                  sync_ts=datetime(today.year, today.month, today.day, 7, 0))

    f = alice.get(f"/api/day/{today.isoformat()}").json()["forecast"]

    assert f["baseline_activity"] == 0 and f["activity_left"] == 0


def test_usage_splits_forecast_accuracy_by_training(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'u.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id=1, email="t@example.com"))
    today = date.today()
    d1, d2 = today - timedelta(days=1), today - timedelta(days=2)
    db.add_all([
        DailySummary(user_id=1, date=d1, kcal_total_garmin=3000, forecast_total_kcal=2700, complete=True),
        DailySummary(user_id=1, date=d2, kcal_total_garmin=2000, forecast_total_kcal=2100, complete=True),
        Activity(user_id=1, date=d1, type="cycling", duration_s=3600, kcal_garmin=900,
                 source="garmin", garmin_id="r1"),
    ])
    db.commit()

    stats = usage._stats_model_vs_measurement(db, {1}, today)
    assert stats["forecast_ratio_training"]["n"] == 1
    assert stats["forecast_ratio_training"]["median"] == 0.9
    assert stats["forecast_ratio_rest"]["n"] == 1
    assert stats["forecast_ratio_rest"]["median"] == 1.05
