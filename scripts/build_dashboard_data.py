"""
Builds data/processed/dashboard_data.json for the model-comparison dashboard.

Runs its own walk-forward evaluation rather than reusing the
data/processed/*_backtest_summary.json files, for two reasons found during a
pre-launch audit:

1. Those files are stale — last regenerated at the initial commit, before a
   later commit expanded matches.parquet. They don't reflect current data.
2. src/evaluation/backtest.py scores Elo on every match (i=0..N-1), while
   backtest_poisson.py and backtest_combined.py skip the first 100 matches
   as a training warm-up (i=100..N-1). Elo's headline number and the other
   two's are therefore not computed on the same fixtures, which makes any
   "combined beats Elo alone" comparison invalid as reported.

This script scores all three models on the identical i>=100 fixture set, so
the dashboard's numbers are directly comparable. It reuses src.models.elo and
src.models.poisson unchanged — only the evaluation harness is new, and it
does not modify or replace the existing backtest scripts.

Usage
-----
  python scripts/build_dashboard_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation.metrics import accuracy_1x2, brier_score_1x2, log_loss_1x2
from src.models.elo import predict_proba, update_ratings
from src.models.poisson import PoissonGoalsModel

ROOT = Path(__file__).resolve().parents[1]
MATCHES_PATH = ROOT / "data" / "processed" / "matches.parquet"
OUTPUT_PATH = ROOT / "data" / "processed" / "dashboard_data.json"

START_RATING = 1500.0
K = 40.0
HOME_ADV = 65.0
DRAW_PROB = 0.23
MIN_TRAIN_MATCHES = 100
ELO_WEIGHT = 0.7
ROLLING_WINDOW = 100
CALIBRATION_BUCKETS = 10  # decile buckets on the predicted-outcome probability


def season_label(date: pd.Timestamp) -> str:
    start_year = date.year if date.month >= 8 else date.year - 1
    return f"{start_year}/{str(start_year + 1)[-2:]}"


def result_for(row_ftr: str, side: str) -> int:
    """1 if `side` ('home'/'draw'/'away') is what actually happened, else 0."""
    return int({"home": "H", "draw": "D", "away": "A"}[side] == row_ftr)


def predicted_outcome_prob(p_home: float, p_draw: float, p_away: float) -> tuple[str, float]:
    """The side the model favoured, and the probability it assigned to it."""
    options = [("home", p_home), ("draw", p_draw), ("away", p_away)]
    return max(options, key=lambda x: x[1])


def rolling_accuracy(records: list[dict], window: int) -> list[dict]:
    """Rolling correct/window accuracy, one point per `window` matches (non-overlapping)."""
    out = []
    for start in range(0, len(records), window):
        chunk = records[start : start + window]
        if len(chunk) < window // 2:  # drop a too-small tail chunk
            continue
        correct = sum(1 for r in chunk if r["correct"])
        out.append({
            "date": chunk[-1]["date"],
            "accuracy": correct / len(chunk),
            "n": len(chunk),
        })
    return out


def calibration_curve(records: list[dict], buckets: int) -> list[dict]:
    """Predicted-probability decile vs actual observed frequency for that bucket."""
    sorted_recs = sorted(records, key=lambda r: r["predicted_prob"])
    n = len(sorted_recs)
    out = []
    bucket_size = max(1, n // buckets)
    for start in range(0, n, bucket_size):
        chunk = sorted_recs[start : start + bucket_size]
        if not chunk:
            continue
        mean_predicted = sum(r["predicted_prob"] for r in chunk) / len(chunk)
        observed_freq = sum(r["correct"] for r in chunk) / len(chunk)
        out.append({
            "predicted": mean_predicted,
            "observed": observed_freq,
            "n": len(chunk),
        })
    return out


def main() -> None:
    df = pd.read_parquet(MATCHES_PATH)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    ratings: dict[str, float] = {}
    elo_records, poisson_records, combined_records = [], [], []
    per_match_rows = []

    for i, row in df.iterrows():
        home, away, ftr = row["HomeTeam"], row["AwayTeam"], row["FTR"]
        r_home = ratings.get(home, START_RATING)
        r_away = ratings.get(away, START_RATING)

        if i >= MIN_TRAIN_MATCHES:
            elo_home, elo_draw, elo_away = predict_proba(
                r_home=r_home, r_away=r_away, home_adv=HOME_ADV, draw_prob=DRAW_PROB
            )

            train_df = df.iloc[:i].copy()
            poisson_model = PoissonGoalsModel().fit(train_df)
            pred = poisson_model.predict(home, away, max_goals=6, top_n=1)

            comb_home = ELO_WEIGHT * elo_home + (1 - ELO_WEIGHT) * pred.p_home
            comb_draw = ELO_WEIGHT * elo_draw + (1 - ELO_WEIGHT) * pred.p_draw
            comb_away = ELO_WEIGHT * elo_away + (1 - ELO_WEIGHT) * pred.p_away
            tot = comb_home + comb_draw + comb_away
            comb_home, comb_draw, comb_away = comb_home / tot, comb_draw / tot, comb_away / tot

            date_str = row["Date"].strftime("%Y-%m-%d")

            for model_name, records, (p_h, p_d, p_a) in [
                ("elo", elo_records, (elo_home, elo_draw, elo_away)),
                ("poisson", poisson_records, (pred.p_home, pred.p_draw, pred.p_away)),
                ("combined", combined_records, (comb_home, comb_draw, comb_away)),
            ]:
                side, prob = predicted_outcome_prob(p_h, p_d, p_a)
                records.append({
                    "date": date_str,
                    "correct": result_for(ftr, side),
                    "predicted_prob": prob,
                    "p_home": p_h, "p_draw": p_d, "p_away": p_a,
                    "ftr": ftr,
                })

            per_match_rows.append({
                "date": date_str,
                "season": season_label(row["Date"]),
                "home_team": home,
                "away_team": away,
                "ftr": ftr,
                "elo_p_home": elo_home, "elo_p_draw": elo_draw, "elo_p_away": elo_away,
                "poisson_p_home": pred.p_home, "poisson_p_draw": pred.p_draw, "poisson_p_away": pred.p_away,
                "combined_p_home": comb_home, "combined_p_draw": comb_draw, "combined_p_away": comb_away,
            })

        r_home_new, r_away_new = update_ratings(
            r_home=r_home, r_away=r_away,
            goals_home=int(row["FTHG"]), goals_away=int(row["FTAG"]),
            k=K, home_adv=HOME_ADV,
        )
        ratings[home], ratings[away] = r_home_new, r_away_new

    def metrics_for(records: list[dict], p_key_prefix: str) -> dict:
        rows = [{"FTR": r["ftr"], "p_home": r["p_home"], "p_draw": r["p_draw"], "p_away": r["p_away"]} for r in records]
        return {
            "matches": len(rows),
            "accuracy": accuracy_1x2(rows),
            "brier_score": brier_score_1x2(rows),
            "log_loss": log_loss_1x2(rows),
        }

    summary = {
        "elo": metrics_for(elo_records, "elo"),
        "poisson": metrics_for(poisson_records, "poisson"),
        "combined": metrics_for(combined_records, "combined"),
    }

    seasons = sorted({r["season"] for r in per_match_rows})
    season_breakdown = {}
    for season in seasons:
        idx = [j for j, r in enumerate(per_match_rows) if r["season"] == season]
        season_breakdown[season] = {
            "elo": metrics_for([elo_records[j] for j in idx], "elo"),
            "poisson": metrics_for([poisson_records[j] for j in idx], "poisson"),
            "combined": metrics_for([combined_records[j] for j in idx], "combined"),
        }

    output = {
        "generated_from_matches": len(df),
        "eval_matches": len(elo_records),
        "min_train_matches": MIN_TRAIN_MATCHES,
        "elo_weight": ELO_WEIGHT,
        "seasons": seasons,
        "summary": summary,
        "season_breakdown": season_breakdown,
        "rolling_accuracy": {
            "elo": rolling_accuracy(elo_records, ROLLING_WINDOW),
            "poisson": rolling_accuracy(poisson_records, ROLLING_WINDOW),
            "combined": rolling_accuracy(combined_records, ROLLING_WINDOW),
        },
        "calibration": {
            "elo": calibration_curve(elo_records, CALIBRATION_BUCKETS),
            "poisson": calibration_curve(poisson_records, CALIBRATION_BUCKETS),
            "combined": calibration_curve(combined_records, CALIBRATION_BUCKETS),
        },
        "matches": per_match_rows,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))

    print(f"Evaluated {len(elo_records)} matches (of {len(df)} total, first {MIN_TRAIN_MATCHES} used as warm-up only)")
    for name, m in summary.items():
        print(f"  {name:9s}  acc={m['accuracy']:.4f}  brier={m['brier_score']:.4f}  logloss={m['log_loss']:.4f}")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
