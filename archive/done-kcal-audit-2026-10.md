# Done — kcal accuracy audit (2026-10)

Fixes that came out of the 2026-10-04 review of the daily kcal prediction
against production tester data. Newest on top.

## Stored forecast keeps the hour it was made for (26.0.1)

- Problem: `forecast_total_kcal` is written on the first visit of the day with
  no time, so `/usage` mixed 07:00 predictions with near-final 22:00 numbers.
- New column `DailySummary.forecast_hour_local` (local sync hour, 0.1 h),
  written together with the forecast; additive migration, old rows stay NULL.
- Stats: `/usage` shows the snapshot hour distribution and forecast/actual for
  morning snapshots only (before 12:00); "Moje dni" shows the hour per day.
- Privacy note unchanged: the hour is derived from the sync time we already store.
- Test: `tests/test_forecast_hour.py`.

## Day forecast expects the user's usual workout (26.0.0)

- Problem: the forecast was measured + resting + NEAT, never a workout. For the
  Garmin tester (trains ~24 of 28 days) median forecast/actual was 0.65,
  error −1016 kcal; on rest days it was 0.98, so the workout was the whole gap.
- New term: median net workout kcal of the last 7 closed days, minus what is
  already done today, spread over the rest of the waking window (6–23).
- Median, not mean, and no share < 1: backtest on production data at 08:00 moved
  median ratio 0.78 → 0.965 and days outside ±15% from 64% to 42%; occasional
  trainers get 0. Conservatism stays explicit (floor to 50, calibration clamp).
- `mobile.html` explains the term in the target breakdown.
- Stats: `/usage` splits forecast/actual into training and rest days.
- Test: `tests/test_forecast_workout.py`.

## Strava workouts no longer zeroed by inflated duration (25.2.3)

- Problem: Strava's `elapsed_time` includes pauses; the resting part subtracted
  in `day._activity_resting_kcal` scales with duration and exceeded the gross
  kcal, so 3 of 12 Strava activities counted as 0 kcal.
- Strava sync now stores `moving_time` (falls back to `elapsed_time`); a resync
  rewrites rows still inside the sync window.
- Estimated resting (not the watch's own per-activity value) is capped at
  `MAX_RESTING_SHARE` = 50% of gross kcal: a logged workout is at least ~2 MET.
- Stats: `/usage` shows synced activities whose resting estimate hit the cap.
- Test: `tests/test_resting_cap.py`.

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
