"""Manual activity entries that duplicate a synced one.

Testers log a workout by hand and later Strava/Garmin syncs the same workout;
both used to count towards expenditure (2026-10-04 audit: 4 of 5 days of the
Strava tester, one ride counted as 3026 kcal instead of ~1700). Activities have
no start time, so a match is: same day, same sport family, similar distance
(or similar duration when either side has no distance). The synced entry wins
because it is measured; the manual one stays in the database and in the UI,
flagged, so the user can see why it does not count.
"""

from collections.abc import Sequence
from typing import Protocol

DISTANCE_TOLERANCE = 0.20
DURATION_TOLERANCE = 0.25

_FAMILIES = (
    ("cycling", ("cycl", "biking", "ride")),
    ("running", ("run",)),
    ("walking", ("walk", "hik")),
    ("swimming", ("swim",)),
    ("strength", ("strength", "training", "crossfit")),
)


class _ActivityLike(Protocol):
    date: object
    type: str
    duration_s: int
    distance_m: float | None
    source: str


def sport_family(activity_type: str) -> str:
    t = activity_type.lower()
    for family, needles in _FAMILIES:
        if any(n in t for n in needles):
            return family
    return t


def _close(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance * max(a, b)


def _same_workout(manual: _ActivityLike, synced: _ActivityLike) -> bool:
    if manual.date != synced.date or sport_family(manual.type) != sport_family(synced.type):
        return False
    if manual.distance_m and synced.distance_m:
        return _close(manual.distance_m, synced.distance_m, DISTANCE_TOLERANCE)
    if manual.duration_s and synced.duration_s:
        return _close(manual.duration_s, synced.duration_s, DURATION_TOLERANCE)
    return False


def manual_duplicates(activities: Sequence[_ActivityLike]) -> list[_ActivityLike]:
    """Manual entries shadowed by a synced activity. Each synced activity
    shadows at most one manual entry (two hand-logged rides on a day with one
    synced ride: only one of them is a duplicate)."""
    synced = [a for a in activities if a.source != "manual"]
    used: set[int] = set()
    duplicates = []
    for m in (a for a in activities if a.source == "manual"):
        for i, s in enumerate(synced):
            if i not in used and _same_workout(m, s):
                used.add(i)
                duplicates.append(m)
                break
    return duplicates


def without_manual_duplicates(activities: Sequence[_ActivityLike]) -> list[_ActivityLike]:
    dup_ids = {id(a) for a in manual_duplicates(activities)}
    return [a for a in activities if id(a) not in dup_ids]
