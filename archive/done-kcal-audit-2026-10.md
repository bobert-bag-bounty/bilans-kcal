# Done — kcal accuracy audit (2026-10)

Fixes that came out of the 2026-10-04 review of the daily kcal prediction
against production tester data. Newest on top.

## Calibration no longer crashes for users without a Garmin daily total (25.2.1)

- Problem: `catch_up` computed `kcal_out` from `kcal_total_garmin` before
  checking whether the day was valid. Strava and manual users have NULL there,
  so every run raised TypeError (25x `calibration_error`, all from the Strava tester).
- Fix: validate the day first, compute `kcal_out` only for valid days.
- These users still do not get adaptive calibration (it needs a measured daily
  total), but the cursor now advances instead of rolling back each time.
- Stats: `calibration_error` on `/usage` should drop to 0.
- Test: `tests/test_calibration_non_garmin.py`.
