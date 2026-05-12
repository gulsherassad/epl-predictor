from pathlib import Path
import json

import pandas as pd

from src.evaluation.metrics import accuracy_1x2, log_loss_1x2, brier_score_1x2
from src.models.poisson import PoissonGoalsModel


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    matches_path = project_root() / "data" / "processed" / "matches.parquet"
    df = pd.read_parquet(matches_path)

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    rows = []

    min_train_matches = 100

    for i in range(min_train_matches, len(df)):
        train_df = df.iloc[:i].copy()
        row = df.iloc[i]

        home = row["HomeTeam"]
        away = row["AwayTeam"]

        model = PoissonGoalsModel().fit(train_df)
        pred = model.predict(home, away, max_goals=6, top_n=5)

        rows.append(
            {
                "Date": row["Date"],
                "HomeTeam": home,
                "AwayTeam": away,
                "FTR": row["FTR"],
                "p_home": float(pred.p_home),
                "p_draw": float(pred.p_draw),
                "p_away": float(pred.p_away),
                "xg_home": float(pred.xg_home),
                "xg_away": float(pred.xg_away),
            }
        )

    acc = accuracy_1x2(rows)
    ll = log_loss_1x2(rows)
    brier = brier_score_1x2(rows)

    print("Poisson backtest results")
    print("Matches:", len(rows))
    print("Accuracy (1X2):", round(acc, 4))
    print("Log loss:", round(ll, 4))
    print("Brier score:", round(brier, 4))

    processed_dir = project_root() / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    pred_df = pd.DataFrame(rows)
    pred_path = processed_dir / "poisson_predictions.parquet"
    pred_df.to_parquet(pred_path, index=False)
    print("Saved predictions to:", pred_path)

    summary = {
        "model": "poisson",
        "matches": len(rows),
        "accuracy_1x2": float(acc),
        "log_loss": float(ll),
        "brier_score": float(brier),
        "min_train_matches": min_train_matches,
        "max_goals": 6,
    }

    summary_path = processed_dir / "poisson_backtest_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print("Saved summary to:", summary_path)


if __name__ == "__main__":
    main()