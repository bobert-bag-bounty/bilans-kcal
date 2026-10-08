"""Inflated activity durations (2026-10-04 audit): Strava elapsed_time with
pauses made the subtracted resting part exceed the workout's gross kcal, so
3 of 12 Strava activities counted as 0 kcal."""
import json
from datetime import date
from types import SimpleNamespace

from app.db import Base
from app.models import Activity, User
from app.providers import strava as strava_provider
from app.services import usage
from app.services import settings as settings_service
from app.services.day import MAX_RESTING_SHARE, _activity_resting_kcal
from tests.test_strava import db  # noqa: F401  (fixture)

BMR = 1800.0


def act(duration_s, kcal, kcal_bmr=None):
    return SimpleNamespace(duration_s=duration_s, kcal_garmin=kcal, kcal_bmr_garmin=kcal_bmr)


def test_ride_with_forgotten_stop_keeps_half_of_its_kcal():
    """9.7 h elapsed, 354 kcal: resting estimate 727 used to zero it out."""
    resting = _activity_resting_kcal(act(34910, 354), None, BMR)
    assert resting == MAX_RESTING_SHARE * 354
    assert 354 - resting > 0


def test_plausible_workout_is_not_capped():
    a = act(10507, 1724)                       # 2.9 h, 1724 kcal
    assert _activity_resting_kcal(a, None, BMR) == BMR / 86400 * 10507


def test_cap_applies_to_garmin_daily_bmr_fallback_too():
    summary = SimpleNamespace(kcal_bmr_garmin=2000)
    assert _activity_resting_kcal(act(36000, 515), summary, BMR) == MAX_RESTING_SHARE * 515


def test_watch_per_activity_resting_is_trusted_as_is():
    assert _activity_resting_kcal(act(36000, 515, kcal_bmr=400), None, BMR) == 400


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_strava_uses_moving_time_not_elapsed_time(db, monkeypatch):  # noqa: F811
    blob = {"access_token": "t", "refresh_token": "r", "expires_at": 9999999999}
    settings_service.set_setting(db, 1, strava_provider.STRAVA_TOKENS_KEY, json.dumps(blob))
    item = {"id": 1, "sport_type": "Ride", "start_date_local": "2026-09-08T10:00:00Z",
            "elapsed_time": 34910, "moving_time": 3500, "distance": 13059.3, "calories": 354}
    pages = iter([[item], []])
    monkeypatch.setattr(strava_provider.httpx, "get", lambda *a, **k: _Resp(next(pages)))

    acts = strava_provider.StravaProvider(1, db).get_activities(date(2026, 9, 8), date(2026, 9, 8))

    assert [a.duration_s for a in acts] == [3500]


def test_strava_falls_back_to_elapsed_time(db, monkeypatch):  # noqa: F811
    blob = {"access_token": "t", "refresh_token": "r", "expires_at": 9999999999}
    settings_service.set_setting(db, 1, strava_provider.STRAVA_TOKENS_KEY, json.dumps(blob))
    item = {"id": 2, "sport_type": "Run", "start_date_local": "2026-09-08T10:00:00Z",
            "elapsed_time": 2290, "distance": 6108.5, "calories": 469}
    pages = iter([[item], []])
    monkeypatch.setattr(strava_provider.httpx, "get", lambda *a, **k: _Resp(next(pages)))

    acts = strava_provider.StravaProvider(1, db).get_activities(date(2026, 9, 8), date(2026, 9, 8))

    assert [a.duration_s for a in acts] == [2290]

def test_usage_counts_resting_capped_activities(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path / 'cap.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id=1, email="t@example.com"))
    today = date.today()
    db.add_all([
        Activity(user_id=1, date=today, type="cycling", duration_s=34910, kcal_garmin=354,
                 source="garmin", garmin_id="strava-1"),           # inflated -> capped
        Activity(user_id=1, date=today, type="cycling", duration_s=10507, kcal_garmin=1724,
                 source="garmin", garmin_id="strava-2"),           # plausible
        Activity(user_id=1, date=today, type="cycling", duration_s=36000, kcal_garmin=515,
                 kcal_bmr_garmin=400, source="garmin", garmin_id="g-3"),  # watch value, not estimated
    ])
    db.commit()

    stats = usage._stats_model_vs_measurement(db, {1}, today)["resting_capped"]
    assert stats == {"synced_estimated_30d": 2, "capped_30d": 1}
