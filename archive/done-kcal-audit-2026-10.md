# Done — kcal accuracy audit (2026-10)

Fixes that came out of the 2026-10-04 review of the daily kcal prediction
against production tester data. Newest on top.

## Manual workout that was also synced counts once (25.2.2)

- Problem: a workout logged by hand and later synced from Strava/Garmin was
  summed twice (Strava tester: 4 of 5 days, one ride 3026 kcal instead of ~1700).
- Match without start times: same day + sport family + distance within 20%
  (duration within 25% when a distance is missing); one synced workout shadows
  at most one manual entry. The synced one wins because it is measured.
- Applied in `day.day_energy` (Today, Trends) and `calibration._day_kcal_out`;
  the manual row is kept and shown greyed out in `mobile.html` with a note.
- Stats: `/usage` shows manual entries flagged as duplicates over 30 days.
- Test: `tests/test_activity_dedup.py`.

## Calibration no longer crashes for users without a Garmin daily total (25.2.1)

- Problem: `catch_up` computed `kcal_out` from `kcal_total_garmin` before
  checking whether the day was valid. Strava and manual users have NULL there,
  so every run raised TypeError (25x `calibration_error`, all from the Strava tester).
- Fix: validate the day first, compute `kcal_out` only for valid days.
- These users still do not get adaptive calibration (it needs a measured daily
  total), but the cursor now advances instead of rolling back each time.
- Stats: `calibration_error` on `/usage` should drop to 0.
- Test: `tests/test_calibration_non_garmin.py`.
