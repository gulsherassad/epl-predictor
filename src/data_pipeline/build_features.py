from __future__ import annotations

from pathlib import Path
import pandas as pd


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def processed_dir() -> Path:
    return project_root() / "data" / "processed"


def main() -> None:
    out_dir = processed_dir()
    in_path = out_dir / "matches_clean.csv"
    if not in_path.exists():
        raise FileNotFoundError(
            f"Missing {in_path}. Run clean_matches.py first."
        )

    df = pd.read_csv(in_path)

    # Ensure Date is datetime, then sort
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    out_path = out_dir / "matches.parquet"

    # Requires pyarrow installed, which you already added.
    df.to_parquet(out_path, index=False)

    print(f"Saved parquet: {out_path}")
    print(f"Rows: {len(df)}")
    print("Columns:", list(df.columns))


if __name__ == "__main__":
    main()
