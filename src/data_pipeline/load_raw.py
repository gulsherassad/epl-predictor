from __future__ import annotations

from pathlib import Path
import pandas as pd


REQUIRED_COLS = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def raw_dir() -> Path:
    return project_root() / "data" / "raw"


def processed_dir() -> Path:
    return project_root() / "data" / "processed"


def find_csv_files(folder: Path) -> list[Path]:
    if not folder.exists():
        raise FileNotFoundError(f"Missing folder: {folder}")
    files = sorted(folder.glob("*.csv"))
    return files


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Football-Data CSVs usually have consistent names, but normalize whitespace just in case.
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    return df


def load_one_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = normalize_columns(df)

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path.name} is missing columns: {missing}. "
            f"Found columns: {list(df.columns)}"
        )

    # Keep only what we need for now, extra columns can come later.
    df = df[REQUIRED_COLS].copy()

    # Add a source column so you can debug merges later.
    df["source_file"] = path.name
    return df


def main() -> None:
    in_dir = raw_dir()
    out_dir = processed_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    files = find_csv_files(in_dir)
    if not files:
        raise FileNotFoundError(f"No CSV files found in {in_dir}")

    frames: list[pd.DataFrame] = []
    for f in files:
        print(f"Loading: {f.name}")
        frames.append(load_one_csv(f))

    merged = pd.concat(frames, ignore_index=True)

    out_path = out_dir / "raw_merged.csv"
    merged.to_csv(out_path, index=False)
    print(f"Saved merged raw file: {out_path}")
    print(f"Rows: {len(merged)}")


if __name__ == "__main__":
    main()
