import json
import sys
from pathlib import Path

import pandas as pd


COLUMN_ALIASES = {
    "home_team": ["home_team", "HomeTeam", "team_home", "home"],
    "away_team": ["away_team", "AwayTeam", "team_away", "away"],
    "home_goals": ["home_goals", "FTHG", "HG", "goals_home"],
    "away_goals": ["away_goals", "FTAG", "AG", "goals_away"],
    "home_xg": ["home_xg", "xg_home", "xG_home"],
    "away_xg": ["away_xg", "xg_away", "xG_away"],
}

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


def find_column(df: pd.DataFrame, logical_name: str) -> str | None:
    for candidate in COLUMN_ALIASES[logical_name]:
        if candidate in df.columns:
            return candidate
    return None


def load_matches(input_path: Path) -> pd.DataFrame:
    if input_path.suffix == ".csv":
        return pd.read_csv(input_path)

    if input_path.suffix == ".parquet":
        return pd.read_parquet(input_path)

    raise ValueError("Input file must be .csv or .parquet")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: python scripts/build_team_strengths.py <input_file> [output_file]"
        )

    input_path = Path(sys.argv[1])
    output_path = (
        Path(sys.argv[2])
        if len(sys.argv) >= 3
        else Path("src/data/team_strengths.json")
    )

    df = load_matches(input_path)

    rename_map: dict[str, str] = {}
    for logical_name in ["home_team", "away_team", "home_goals", "away_goals"]:
        actual = find_column(df, logical_name)
        if actual is None:
            raise ValueError(f"Could not find a column for {logical_name}")
        rename_map[actual] = logical_name

    home_xg_col = find_column(df, "home_xg")
    away_xg_col = find_column(df, "away_xg")

    if home_xg_col:
        rename_map[home_xg_col] = "home_xg"
    if away_xg_col:
        rename_map[away_xg_col] = "away_xg"

    df = df.rename(columns=rename_map).copy()

    df["home_team"] = df["home_team"].replace(TEAM_NAME_MAP)
    df["away_team"] = df["away_team"].replace(TEAM_NAME_MAP)

    df["home_goals"] = pd.to_numeric(df["home_goals"], errors="coerce")
    df["away_goals"] = pd.to_numeric(df["away_goals"], errors="coerce")

    df = df[df["home_goals"].notna() & df["away_goals"].notna()].copy()

    if "home_xg" in df.columns:
        df["home_xg"] = pd.to_numeric(df["home_xg"], errors="coerce")
    if "away_xg" in df.columns:
        df["away_xg"] = pd.to_numeric(df["away_xg"], errors="coerce")

    if "home_xg" in df.columns and "away_xg" in df.columns:
        home_metric = df["home_xg"].fillna(df["home_goals"]).astype(float)
        away_metric = df["away_xg"].fillna(df["away_goals"]).astype(float)
        metric_name = "xg"
    else:
        home_metric = df["home_goals"].astype(float)
        away_metric = df["away_goals"].astype(float)
        metric_name = "goals"

    league_home_avg = float(home_metric.mean())
    league_away_avg = float(away_metric.mean())

    home_rows = pd.DataFrame(
        {
            "team": df["home_team"],
            "scored": home_metric,
            "conceded": away_metric,
            "attack_baseline": league_home_avg,
            "defence_baseline": league_away_avg,
        }
    )

    away_rows = pd.DataFrame(
        {
            "team": df["away_team"],
            "scored": away_metric,
            "conceded": home_metric,
            "attack_baseline": league_away_avg,
            "defence_baseline": league_home_avg,
        }
    )

    team_rows = pd.concat([home_rows, away_rows], ignore_index=True)

    strengths: dict[str, dict[str, float]] = {}

    for team, group in team_rows.groupby("team"):
        matches = int(len(group))

        avg_scored = float(group["scored"].mean())
        avg_conceded = float(group["conceded"].mean())
        avg_attack_baseline = float(group["attack_baseline"].mean())
        avg_defence_baseline = float(group["defence_baseline"].mean())

        raw_attack = avg_scored / avg_attack_baseline if avg_attack_baseline > 0 else 1.0
        raw_defence = (
            avg_defence_baseline / avg_conceded if avg_conceded > 0 else 1.0
        )

        shrink = min(matches / 20.0, 1.0)
        attack = 1.0 + (raw_attack - 1.0) * shrink
        defence = 1.0 + (raw_defence - 1.0) * shrink

        strengths[team] = {
            "attack": round(clamp(attack, 0.75, 1.35), 4),
            "defence": round(clamp(defence, 0.75, 1.35), 4),
            "matches": matches,
        }

    output = {
        "meta": {
            "metric": metric_name,
            "base_home_xg": round(league_home_avg, 4),
            "base_away_xg": round(league_away_avg, 4),
        },
        "teams": dict(sorted(strengths.items())),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote team strengths to {output_path}")


if __name__ == "__main__":
    main()