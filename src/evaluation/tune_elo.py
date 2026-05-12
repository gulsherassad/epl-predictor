from pathlib import Path
import pandas as pd

from src.models.elo import predict_proba, update_ratings
from src.evaluation.metrics import accuracy_1x2, log_loss_1x2, brier_score_1x2


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_matches() -> pd.DataFrame:
    path = project_root() / "data" / "processed" / "matches.parquet"
    df = pd.read_parquet(path)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def run_backtest(df: pd.DataFrame, k: float, home_adv: float, draw_prob: float) -> dict:
    START_RATING = 1500.0
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
            home_adv=home_adv,
            draw_prob=draw_prob,
        )

        rows.append(
            {
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
            k=k,
            home_adv=home_adv,
        )

        ratings[home] = r_home_new
        ratings[away] = r_away_new

    acc = accuracy_1x2(rows)
    ll = log_loss_1x2(rows)
    brier = brier_score_1x2(rows)

    return {
        "k": k,
        "home_adv": home_adv,
        "draw_prob": draw_prob,
        "matches": len(rows),
        "accuracy": acc,
        "log_loss": ll,
        "brier": brier,
    }


def main() -> None:
    df = load_matches()

    # Small grid. Fast and enough to find a better baseline.
    k_values = [10.0, 15.0, 20.0, 25.0, 30.0, 40.0]
    home_adv_values = [0.0, 25.0, 50.0, 65.0, 80.0, 100.0]
    draw_probs = [0.20, 0.23, 0.25, 0.27, 0.30]

    results = []
    total = len(k_values) * len(home_adv_values) * len(draw_probs)
    done = 0

    for k in k_values:
        for ha in home_adv_values:
            for dp in draw_probs:
                done += 1
                r = run_backtest(df, k=k, home_adv=ha, draw_prob=dp)
                results.append(r)
                print(
                    f"{done}/{total}  k={k:.1f}  home_adv={ha:.1f}  draw={dp:.2f}  "
                    f"logloss={r['log_loss']:.4f}  brier={r['brier']:.4f}  acc={r['accuracy']:.4f}"
                )

    res_df = pd.DataFrame(results)

    best_logloss = res_df.sort_values(["log_loss", "brier"], ascending=[True, True]).iloc[0]
    best_brier = res_df.sort_values(["brier", "log_loss"], ascending=[True, True]).iloc[0]
    best_acc = res_df.sort_values(["accuracy", "log_loss"], ascending=[False, True]).iloc[0]

    print("")
    print("BEST BY LOG LOSS")
    print(best_logloss.to_dict())

    print("")
    print("BEST BY BRIER")
    print(best_brier.to_dict())

    print("")
    print("BEST BY ACCURACY")
    print(best_acc.to_dict())

    out_path = project_root() / "data" / "processed" / "elo_tuning_results.csv"
    res_df.to_csv(out_path, index=False)
    print("")
    print("Saved full grid results to:", out_path)


if __name__ == "__main__":
    main()
