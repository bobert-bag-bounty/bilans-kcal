"""Manual activity entries that duplicate a synced workout (2026-10-04 audit).
Cases mirror the Strava tester's real days."""
from datetime import date, timedelta
from types import SimpleNamespace

from app.db import Base
from app.models import Activity, User
from app.services import usage
from app.services.activity_dedup import manual_duplicates, sport_family, without_manual_duplicates
from app.services.calibration import _day_kcal_out
from app.services.day import day_energy

D = date(2026, 9, 7)


def act(source, type_, duration_s, distance_m, kcal, day=D):
    return SimpleNamespace(date=day, type=type_, duration_s=duration_s, distance_m=distance_m,
                           kcal_garmin=kcal, source=source, steps=None, kcal_bmr_garmin=None)


def test_same_ride_logged_by_hand_and_synced_is_a_duplicate():
    manual = act("manual", "cycling", 9300, 75000, 1302)
    synced = act("garmin", "cycling", 10507, 74014, 1724)
    assert manual_duplicates([manual, synced]) == [manual]
    assert without_manual_duplicates([manual, synced]) == [synced]


def test_same_run_is_a_duplicate():
    assert manual_duplicates([act("manual", "running", 2340, 6100, 435),
                              act("garmin", "running", 2290, 6108, 469)])


def test_ride_with_forgotten_stop_matches_on_distance_not_duration():
    """Strava elapsed time 10 h vs 1 h logged by hand; 17 vs 18.6 km."""
    assert manual_duplicates([act("manual", "cycling", 3600, 17000, 390),
                              act("garmin", "cycling", 35968, 18573, 515)])


def test_clearly_different_distance_is_a_separate_workout():
    assert not manual_duplicates([act("manual", "cycling", 3600, 20000, 396),
                                  act("garmin", "cycling", 4935, 36629, 806)])


def test_different_sport_or_day_is_not_a_duplicate():
    synced = act("garmin", "cycling", 3600, 20000, 500)
    assert not manual_duplicates([act("manual", "running", 3600, 20000, 500), synced])
    assert not manual_duplicates([act("manual", "cycling", 3600, 20000, 500,
                                      day=D + timedelta(days=1)), synced])


def test_duration_is_used_when_distance_missing():
    assert manual_duplicates([act("manual", "strength_training", 3600, None, 300),
                              act("garmin", "strength_training", 3759, 0.0, 498)])


def test_one_synced_workout_shadows_only_one_manual_entry():
    m1 = act("manual", "cycling", 3600, 20000, 400)
    m2 = act("manual", "cycling", 3600, 20500, 400)
    assert len(manual_duplicates([m1, m2, act("garmin", "cycling", 3700, 20200, 500)])) == 1


def test_garmin_type_keys_map_to_families():
    assert sport_family("road_biking") == sport_family("indoor_cycling") == "cycling"
    assert sport_family("trail_running") == "running"
    assert sport_family("lap_swimming") == "swimming"


def test_calibration_kcal_out_skips_duplicate_manual_kcal():
    summary = SimpleNamespace(kcal_total_garmin=3000)
    acts = [act("manual", "cycling", 9300, 75000, 1302), act("garmin", "cycling", 10507, 74014, 1724)]
    assert _day_kcal_out(summary, acts) == 3000


def test_day_energy_counts_duplicate_once():
    profile = SimpleNamespace(birth_year=1977, height_cm=168, sex="F")
    summary = SimpleNamespace(kcal_total_garmin=None, kcal_bmr_garmin=None, steps=None, complete=True)
    synced = act("garmin", "cycling", 10507, 74014, 1724)
    with_dup = day_energy(profile, 70.0, D, summary,
                          [act("manual", "cycling", 9300, 75000, 1302), synced], [], D)
    alone = day_energy(profile, 70.0, D, summary, [synced], [], D)
    assert with_dup.kcal_out == alone.kcal_out
    assert with_dup.manual_kcal == 0


def test_usage_counts_duplicates(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path / 'u.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id=1, email="t@example.com"))
    today = date.today()
    db.add_all([
        Activity(user_id=1, date=today, type="cycling", duration_s=9300, distance_m=75000,
                 kcal_garmin=1302, source="manual", garmin_id="m1"),
        Activity(user_id=1, date=today, type="cycling", duration_s=10507, distance_m=74014,
                 kcal_garmin=1724, source="garmin", garmin_id="strava-1"),
        Activity(user_id=1, date=today, type="swimming", duration_s=3600, distance_m=2000,
                 kcal_garmin=576, source="manual", garmin_id="m2"),
    ])
    db.commit()

    stats = usage._stats_model_vs_measurement(db, {1}, today)["manual_dedup"]
    assert stats == {"manual_30d": 2, "duplicates_30d": 1, "users": 1}
