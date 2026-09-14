# In-map unit HP write attempt — 2026-09-14

- Target PID: 38352; game remained responsive.
- Requested operation: write selected unit HP to its current value 650 with current/max guards.
- Result: not completed. The 3.0 engine executor returned `status=1` timeout before a verified write/readback result.
- Latest diagnostic log: `log/native-helper-20260914-130957-061-pid38352.log`.
- No HP change is claimed; no follow-up write retry was issued.
- Added session-level native timeout circuit breaker so later operations fail fast or use read-only indexed fallback instead of repeatedly waiting.
- Regression after change: 46 passed.
