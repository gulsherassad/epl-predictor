"""
Downloads completed EPL season CSVs from football-data.co.uk and rebuilds
data/processed/matches.parquet so the prediction model stays current.

No API key required — football-data.co.uk publishes free season files in the
same format as the project's existing raw CSVs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

KEEP_COLUMNS = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
FIRST_SEASON = 2021  # earliest season we track


def current_season() -> int:
    """Return the start year of the current EPL season.

    The season starting in August 2025 runs through May 2026, so its year is 2025.
    Before August we're still in the previous year's season.
    """
    now = datetime.now(timezone.utc)
    return now.year if now.month >= 8 else now.year - 1


def season_csv_url(season: int) -> str:
    """football-data.co.uk URL for a season, e.g. 2025 → .../2526/E0.csv"""
    s = f"{str(season)[2:]}{str(season + 1)[2:]}"
    return f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv"


def season_filename(season: int) -> Path:
    """Local path for a season CSV, e.g. 2025 → data/raw/EPL_25:26.csv"""
    s = str(season)[2:]
    e = str(season + 1)[2:]
    return RAW_DIR / f"EPL_{s}:{e}.csv"


def fetch_season_csv(season: int, timeout: int = 30) -> tuple[Path, int]:
    """Download a season CSV and save it to data/raw/.

    Returns (local_path, completed_match_count).
    Raises httpx.HTTPError on network/HTTP failure.
    """
    url = season_csv_url(season)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()

    path = season_filename(season)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)

    df = pd.read_csv(path)
    df["FTHG"] = pd.to_numeric(df.get("FTHG"), errors="coerce")
    df["FTAG"] = pd.to_numeric(df.get("FTAG"), errors="coerce")
    completed = int(df["FTHG"].notna().sum())
    return path, completed


def rebuild_parquet() -> tuple[int, str]:
    """Combine all raw EPL CSVs into data/processed/matches.parquet.

    Returns (total_row_count, latest_match_date_str).
    """
    files = sorted(RAW_DIR.glob("EPL_*.csv"))
    frames: list[pd.DataFrame] = []

    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if any(c not in df.columns for c in KEEP_COLUMNS):
            continue
        df = df[KEEP_COLUMNS].copy()
        df["FTHG"] = pd.to_numeric(df["FTHG"], errors="coerce")
        df["FTAG"] = pd.to_numeric(df["FTAG"], errors="coerce")
        frames.append(df[df["FTHG"].notna() & df["FTAG"].notna()])

    if not frames:
        raise RuntimeError("No valid raw CSV files found in data/raw/.")

    combined = pd.concat(frames, ignore_index=True)
    combined["Date"] = pd.to_datetime(combined["Date"], dayfirst=True, errors="coerce")
    combined = (
        combined.dropna(subset=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(PROCESSED_DIR / "matches.parquet", index=False)

    latest = combined["Date"].max().strftime("%Y-%m-%d")
    return len(combined), latest
