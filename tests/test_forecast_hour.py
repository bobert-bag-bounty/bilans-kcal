"""Local hour stored with the first forecast of the day (2026-10-04 audit:
/usage compared forecasts taken at 07:00 and at 22:00 as if they were the same
kind of number)."""
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.db import Base, _migrate
from app.models import DailySummary, User
from app.services import usage
from tests.conftest import app_today
from tests.test_activities_api import _seed_summary, _user_id, clients  # noqa: F401


def _stored(SessionLocal, user_id, day):
    db = SessionLocal()
    try:
        return db.execute(select(DailySummary.forecast_total_kcal, DailySummary.forecast_hour_local)
                          .where(DailySummary.user_id == user_id, DailySummary.date == day)).one()
    finally:
        db.close()


def test_first_forecast_stores_the_sync_hour(clients):  # noqa: F811
    alice, _, SessionLocal = clients
    today = app_today()
    user_id = _user_id(SessionLocal, "alice@example.com")
    _seed_summary(SessionLocal, user_id, today, kcal_total_garmin=811, kcal_active_garmin=60,
                  kcal_bmr_garmin=751, steps=1200, complete=False,
                  sync_ts=datetime(today.year, today.month, today.day, 7, 0))   # 07:00 UTC

    body = alice.get(f"/api/day/{today.isoformat()}").json()

    kcal, hour = _stored(SessionLocal, user_id, today)
    assert kcal == body["forecast_kcal"]
    assert hour in (8.0, 9.0)                       # Europe/Warsaw, CET or CEST


def test_later_visit_keeps_the_first_forecast_and_hour(clients):  # noqa: F811
    alice, _, SessionLocal = clients
    today = app_today()
    user_id = _user_id(SessionLocal, "alice@example.com")
    _seed_summary(SessionLocal, user_id, today, kcal_total_garmin=811, kcal_active_garmin=60,
                  kcal_bmr_garmin=751, steps=1200, complete=False,
                  sync_ts=datetime(today.year, today.month, today.day, 7, 0))
    alice.get(f"/api/day/{today.isoformat()}")
    first = _stored(SessionLocal, user_id, today)

    db = SessionLocal()
    row = db.scalar(select(DailySummary).where(DailySummary.user_id == user_id,
                                               DailySummary.date == today))
    row.kcal_total_garmin, row.sync_ts = 2200, datetime(today.year, today.month, today.day, 18, 0)
    db.commit()
    db.close()
    alice.get(f"/api/day/{today.isoformat()}")

    assert _stored(SessionLocal, user_id, today) == first


def test_migration_adds_forecast_hour_column(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE daily_summary (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, date DATE NOT NULL,
                kcal_total_garmin INTEGER, forecast_total_kcal INTEGER)
        """))
        conn.commit()

    _migrate(engine)

    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(daily_summary)"))]
    assert "forecast_hour_local" in cols


def test_usage_reports_morning_forecasts_and_hours(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'u.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id=1, email="t@example.com"))
    today = date.today()
    db.add_all([
        DailySummary(user_id=1, date=today - timedelta(days=1), kcal_total_garmin=3000,
                     forecast_total_kcal=2400, forecast_hour_local=8.0, complete=True),
        DailySummary(user_id=1, date=today - timedelta(days=2), kcal_total_garmin=3000,
                     forecast_total_kcal=2970, forecast_hour_local=22.0, complete=True),
        DailySummary(user_id=1, date=today - timedelta(days=3), kcal_total_garmin=3000,
                     forecast_total_kcal=2000, complete=True),           # before 26.0.1
    ])
    db.commit()

    stats = usage._stats_model_vs_measurement(db, {1}, today)

    assert stats["forecast_ratio"]["n"] == 3
    assert stats["forecast_ratio_morning"]["n"] == 1
    assert stats["forecast_ratio_morning"]["median"] == 0.8
    assert stats["forecast_hours"]["known"] == 2
