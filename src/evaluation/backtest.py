from pathlib import Path
import json
import pandas as pd

from src.models.elo import predict_proba, update_ratings
from src.evaluation.metrics import accuracy_1x2, log_loss_1x2, brier_score_1x2


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    matches_path = project_root() / "data" / "processed" / "matches.parquet"
    df = pd.read_parquet(matches_path)

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    START_RATING = 1500.0
    K = 40.0
    HOME_ADV = 65.0
    DRAW_PROB = 0.23

    ratings = {}
    rows = []

    for _, row in df.iterrows():
        home = row["HomeTeam"]
        away = row["AwayTeam"]

        r_home = ratings.get(home, START_RATING)
        r_away = ratings.get(away, START_RATING)

        p_home, p_draw, p_away = predict_proba(
            r_home=r_home,
            r_away=r_away,
            home_adv=HOME_ADV,
            draw_prob=DRAW_PROB,
        )

        rows.append(
            {
                "Date": row["Date"],
                "HomeTeam": home,
                "AwayTeam": away,
                "FTR": row["FTR"],
                "p_home": float(p_home),
                "p_draw": float(p_draw),
                "p_away": float(p_away),
            }
        )

        r_home_new, r_away_new = update_ratings(
            r_home=r_home,
            r_away=r_away,
            goals_home=int(row["FTHG"]),
            goals_away=int(row["FTAG"]),
            k=K,
            home_adv=HOME_ADV,
        )

        ratings[home] = r_home_new
        ratings[away] = r_away_new

    acc = accuracy_1x2(rows)
    ll = log_loss_1x2(rows)
    brier = brier_score_1x2(rows)

    print("Backtest results")
    print("Matches:", len(rows))
    print("Accuracy (1X2):", round(acc, 4))
    print("Log loss:", round(ll, 4))
    print("Brier score:", round(brier, 4))

    processed_dir = project_root() / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    pred_df = pd.DataFrame(rows)
    pred_path = processed_dir / "elo_predictions.parquet"
    pred_df.to_parquet(pred_path, index=False)
    print("Saved predictions to:", pred_path)

    summary = {
        "model": "elo",
        "matches": len(rows),
        "accuracy_1x2": float(acc),
        "log_loss": float(ll),
        "brier_score": float(brier),
        "start_rating": START_RATING,
        "k": K,
        "home_adv": HOME_ADV,
        "draw_prob": DRAW_PROB,
    }

    summary_path = processed_dir / "backtest_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print("Saved summary to:", summary_path)


if __name__ == "__main__":
    main()