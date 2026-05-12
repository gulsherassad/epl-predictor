import json
from pathlib import Path
import pandas as pd

RAW_PATH = Path("data/raw/EPL_25:26.csv")
OUTPUT_PATH = Path("src/data/fixtures.json")

TEAM_NAME_MAP = {
    "Brighton": "Brighton & Hove Albion",
    "Ipswich": "Ipswich Town",
    "Leeds": "Leeds United",
    "Leicester": "Leicester City",
    "Luton": "Luton Town",
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Newcastle": "Newcastle United",
    "Norwich": "Norwich City",
    "Nott'm Forest": "Nottingham Forest",
    "Tottenham": "Tottenham Hotspur",
    "Spurs": "Tottenham Hotspur",
    "West Ham": "West Ham United",
    "Wolves": "Wolverhampton Wanderers",
}

def main() -> None:
    if not RAW_PATH.exists():
        raise SystemExit(f"Missing raw file: {RAW_PATH}")

    df = pd.read_csv(RAW_PATH)

    required = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df["FTHG"] = pd.to_numeric(df["FTHG"], errors="coerce")
    df["FTAG"] = pd.to_numeric(df["FTAG"], errors="coerce")

    future_df = df[df["FTHG"].isna() | df["FTAG"].isna()].copy()

    future_df["Date"] = pd.to_datetime(future_df["Date"], errors="coerce", dayfirst=True)
    future_df = future_df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    future_df["HomeTeam"] = future_df["HomeTeam"].replace(TEAM_NAME_MAP)
    future_df["AwayTeam"] = future_df["AwayTeam"].replace(TEAM_NAME_MAP)

    fixtures = []
    for _, row in future_df.iterrows():
        fixtures.append(
            {
                "date": row["Date"].strftime("%Y-%m-%d"),
                "time": str(row["Time"]) if "Time" in future_df.columns and pd.notna(row.get("Time")) else "",
                "home_team": row["HomeTeam"],
                "away_team": row["AwayTeam"],
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(fixtures, indent=2), encoding="utf-8")

    print(f"Wrote fixtures to {OUTPUT_PATH}")
    print(f"Future fixtures: {len(fixtures)}")

if __name__ == "__main__":
    main()