from __future__ import annotations

from pathlib import Path
import pandas as pd


KEEP_COLS = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def processed_dir() -> Path:
    return project_root() / "data" / "processed"


def parse_date_series(s: pd.Series) -> pd.Series:
    # Football-Data typically uses day-first dates like 10/08/24.
    # This handles dd/mm/yy and dd/mm/yyyy.
    dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return dt


def main() -> None:
    out_dir = processed_dir()
    in_path = out_dir / "raw_merged.csv"
    if not in_path.exists():
        raise FileNotFoundError(
            f"Missing {in_path}. Run load_raw.py first."
        )

    df = pd.read_csv(in_path)

    # Keep only essential columns
    df = df[KEEP_COLS].copy()

    # Parse date
    df["Date"] = parse_date_series(df["Date"])

    # Convert goals to integers when possible
    df["FTHG"] = pd.to_numeric(df["FTHG"], errors="coerce")
    df["FTAG"] = pd.to_numeric(df["FTAG"], errors="coerce")

    # Basic cleanup
    df["HomeTeam"] = df["HomeTeam"].astype(str).str.strip()
    df["AwayTeam"] = df["AwayTeam"].astype(str).str.strip()
    df["FTR"] = df["FTR"].astype(str).str.strip()

    # Drop rows that do not have a proper finished match
    df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"])
    df = df[df["FTR"].isin(["H", "D", "A"])]

    # Cast goals to int after dropping NaNs
    df["FTHG"] = df["FTHG"].astype(int)
    df["FTAG"] = df["FTAG"].astype(int)

    # Remove obviously broken rows
    df = df[(df["HomeTeam"] != "nan") & (df["AwayTeam"] != "nan")]
    df = df[df["HomeTeam"] != ""]
    df = df[df["AwayTeam"] != ""]

    # Remove duplicates
    df = df.drop_duplicates(subset=["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"])

    # Sort now or later, either is fine
    df = df.sort_values("Date").reset_index(drop=True)

    out_path = out_dir / "matches_clean.csv"
    df.to_csv(out_path, index=False)

    print(f"Saved cleaned matches: {out_path}")
    print(f"Rows: {len(df)}")
    print("Columns:", list(df.columns))
    print("Date range:", df["Date"].min(), "to", df["Date"].max())


if __name__ == "__main__":
    main()
