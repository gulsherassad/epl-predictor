"""
Downloads the latest EPL results from football-data.co.uk and rebuilds
data/processed/matches.parquet so the model stays current.

No API key required.

Usage
-----
  # Update the current season only (most common)
  python scripts/fetch_latest_results.py

  # Update a specific season
  python scripts/fetch_latest_results.py --season 2025

  # Refresh all seasons from 2021 to now
  python scripts/fetch_latest_results.py --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.updater import (
    FIRST_SEASON,
    current_season,
    fetch_season_csv,
    rebuild_parquet,
    season_csv_url,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch latest EPL results and rebuild the training data."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--all",
        action="store_true",
        help=f"Refresh all seasons from {FIRST_SEASON} to the current one",
    )
    group.add_argument(
        "--season",
        type=int,
        metavar="YEAR",
        help="Start year of the season to update (e.g. 2025 for 2025/26)",
    )
    args = parser.parse_args()

    if args.all:
        seasons = list(range(FIRST_SEASON, current_season() + 1))
    elif args.season:
        seasons = [args.season]
    else:
        seasons = [current_season()]

    print(f"Fetching {len(seasons)} season(s): {seasons}\n")

    any_ok = False
    for season in seasons:
        url = season_csv_url(season)
        print(f"  {season}/{season + 1}  {url}")
        print("  ", end="", flush=True)
        try:
            path, count = fetch_season_csv(season)
            print(f"✓  {count} completed matches saved to {path.name}")
            any_ok = True
        except Exception as e:
            print(f"✗  {e}")

    if not any_ok:
        print("\nNo seasons updated — nothing to rebuild.")
        sys.exit(1)

    print("\nRebuilding matches.parquet …", end=" ", flush=True)
    rows, latest = rebuild_parquet()
    print(f"done.\n")
    print(f"  Total matches : {rows}")
    print(f"  Data through  : {latest}")
    print("\nRestart the server (or POST /refresh) to apply the new data.")


if __name__ == "__main__":
    main()
