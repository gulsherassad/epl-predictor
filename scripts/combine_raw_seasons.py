from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw")
OUTPUT_PATH = Path("data/processed/matches_combined.csv")

KEEP_COLUMNS = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]


def main() -> None:
    files = sorted(RAW_DIR.glob("EPL_*.csv"))

    if not files:
        raise SystemExit("No raw EPL CSV files found in data/raw")

    frames = []

    for file_path in files:
        df = pd.read_csv(file_path)

        missing = [col for col in KEEP_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"{file_path} is missing columns: {missing}")

        df = df[KEEP_COLUMNS].copy()

        df["FTHG"] = pd.to_numeric(df["FTHG"], errors="coerce")
        df["FTAG"] = pd.to_numeric(df["FTAG"], errors="coerce")

        df = df[df["FTHG"].notna() & df["FTAG"].notna()].copy()

        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    combined["Date"] = pd.to_datetime(combined["Date"], errors="coerce", dayfirst=True)
    combined = combined.sort_values("Date").reset_index(drop=True)

    combined["Date"] = combined["Date"].dt.strftime("%Y-%m-%d")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUTPUT_PATH, index=False)

    print(f"Wrote combined matches to {OUTPUT_PATH}")
    print(f"Rows: {len(combined)}")
    print(f"Files used: {len(files)}")


if __name__ == "__main__":
    main()