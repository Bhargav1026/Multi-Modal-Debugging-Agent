# RCA: Login 500s after DB outage

**Root Cause:** Database connection failures (pool timeout / refused).
**Signals:** Repeated `psycopg2.OperationalError`, timeouts, 500 on `/login`.
**Minimal Fix:** Ensure DB service healthy; increase pool size and connection timeout; add circuit breaker on auth flow.
**Suggested Test:** Simulate DB outage and assert graceful 503 retry/backoff instead of 500.