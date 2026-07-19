import hashlib
import logging
import os
from datetime import date

import psycopg

log = logging.getLogger(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL")
SALT = os.environ.get("VISITOR_SALT", "change-me")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    event       TEXT NOT NULL,
    home        TEXT,
    away        TEXT,
    visitor     TEXT,
    day         DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS events_day_idx ON events (day);
"""


def init() -> None:
    if not DATABASE_URL:
        log.warning("DATABASE_URL unset — analytics disabled")
        return
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute(SCHEMA)
    except Exception:
        log.exception("analytics init failed")


def visitor_id(ip: str | None, user_agent: str | None) -> str | None:
    """One-way hash so no raw IPs are stored."""
    if not ip:
        return None
    raw = f"{SALT}:{ip}:{user_agent or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def record(event: str, *, home=None, away=None, visitor=None) -> None:
    """Never let analytics break a request."""
    if not DATABASE_URL:
        return
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=3) as conn:
            conn.execute(
                "INSERT INTO events (event, home, away, visitor) VALUES (%s, %s, %s, %s)",
                (event, home, away, visitor),
            )
    except Exception:
        log.exception("analytics write failed")


def summary() -> dict:
    if not DATABASE_URL:
        return {"enabled": False}
    with psycopg.connect(DATABASE_URL) as conn:
        total = conn.execute(
            "SELECT count(*) FROM events WHERE event = 'predict'"
        ).fetchone()[0]
        visitors = conn.execute(
            "SELECT count(DISTINCT visitor) FROM events WHERE visitor IS NOT NULL"
        ).fetchone()[0]
        week = conn.execute(
            "SELECT count(*) FROM events "
            "WHERE event = 'predict' AND day >= CURRENT_DATE - 7"
        ).fetchone()[0]
        top = conn.execute(
            "SELECT home, away, count(*) AS n FROM events WHERE event = 'predict' "
            "GROUP BY home, away ORDER BY n DESC LIMIT 5"
        ).fetchall()
    return {
        "predictions_total": total,
        "predictions_last_7d": week,
        "unique_visitors": visitors,
        "top_fixtures": [{"home": h, "away": a, "count": n} for h, a, n in top],
    }
