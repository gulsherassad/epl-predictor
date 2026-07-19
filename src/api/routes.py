import json
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from src import analytics
from src.api.schemas import (
    BacktestSummaryResponse,
    HealthResponse,
    PredictResponse,
    PredictScoreResponse,
    TeamsResponse,
)
from src.evaluation.metrics import accuracy_1x2, brier_score_1x2, log_loss_1x2
from src.models.elo import predict_proba, update_ratings
from src.models.poisson import PoissonGoalsModel

router = APIRouter()

START_RATING = 1500.0
K = 40.0
HOME_ADV = 65.0
DRAW_PROB = 0.23
ELO_WEIGHT = 0.7


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def processed_path(name: str) -> Path:
    return project_root() / "data" / "processed" / name


def load_matches() -> pd.DataFrame:
    path = processed_path("matches.parquet")
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run the pipeline first.")
    df = pd.read_parquet(path)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def season_label(date: pd.Timestamp) -> str:
    """A season runs Aug-May, so months before August belong to the prior year."""
    start_year = date.year if date.month >= 8 else date.year - 1
    return f"{start_year}/{str(start_year + 1)[-2:]}"


def compute_current_ratings(df: pd.DataFrame) -> dict:
    ratings = {}

    for _, row in df.iterrows():
        home = row["HomeTeam"]
        away = row["AwayTeam"]

        r_home = ratings.get(home, START_RATING)
        r_away = ratings.get(away, START_RATING)

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

    return ratings


def load_elo_predictions_rows() -> list:
    path = processed_path("elo_predictions.parquet")
    if not path.exists():
        return []
    df = pd.read_parquet(path)
    return df.to_dict(orient="records")


def validate_teams(home: str, away: str, teams: list[str]) -> tuple[str, str]:
    home = home.strip()
    away = away.strip()

    if home not in teams:
        raise HTTPException(status_code=400, detail=f"Unknown home team: {home}")
    if away not in teams:
        raise HTTPException(status_code=400, detail=f"Unknown away team: {away}")
    if home == away:
        raise HTTPException(
            status_code=400,
            detail="home and away must be different teams",
        )

    return home, away


def visitor_from_request(request: Request) -> str | None:
    """Behind Render's proxy the real client IP is in x-forwarded-for."""
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or None
    return analytics.visitor_id(ip, request.headers.get("user-agent"))


def combine_probs(
    elo_home: float,
    elo_draw: float,
    elo_away: float,
    poisson_home: float,
    poisson_draw: float,
    poisson_away: float,
    elo_weight: float = ELO_WEIGHT,
) -> tuple[float, float, float]:
    p_home = elo_weight * float(elo_home) + (1 - elo_weight) * float(poisson_home)
    p_draw = elo_weight * float(elo_draw) + (1 - elo_weight) * float(poisson_draw)
    p_away = elo_weight * float(elo_away) + (1 - elo_weight) * float(poisson_away)

    total = p_home + p_draw + p_away
    if total <= 0:
        return 1 / 3, 1 / 3, 1 / 3

    return p_home / total, p_draw / total, p_away / total


def get_state() -> dict:
    if not hasattr(get_state, "_cache"):
        df = load_matches()
        teams = sorted(set(df["HomeTeam"]).union(set(df["AwayTeam"])))
        ratings = compute_current_ratings(df)
        pred_rows = load_elo_predictions_rows()
        poisson_model = PoissonGoalsModel().fit(df)
        seasons = sorted({season_label(d) for d in df["Date"]})

        get_state._cache = {
            "teams": teams,
            "ratings": ratings,
            "pred_rows": pred_rows,
            "poisson_model": poisson_model,
            "seasons": seasons,
            "match_count": len(df),
        }
    return get_state._cache


def load_backtest_summary() -> dict | None:
    preferred_files = [
        "combined_backtest_summary.json",
        "backtest_summary.json",
    ]

    for filename in preferred_files:
        path = processed_path(filename)
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)

    return None


@router.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@router.get("/teams", response_model=TeamsResponse)
def teams():
    state = get_state()
    return {"teams": state["teams"]}


@router.get("/predict", response_model=PredictResponse)
def predict(
    request: Request,
    background: BackgroundTasks,
    home: str = Query(...),
    away: str = Query(...),
):
    state = get_state()
    home, away = validate_teams(home, away, state["teams"])

    r_home = float(state["ratings"].get(home, START_RATING))
    r_away = float(state["ratings"].get(away, START_RATING))

    elo_home, elo_draw, elo_away = predict_proba(
        r_home=r_home,
        r_away=r_away,
        home_adv=HOME_ADV,
        draw_prob=DRAW_PROB,
    )

    model: PoissonGoalsModel = state["poisson_model"]
    poisson_pred = model.predict(home, away, max_goals=6, top_n=5)

    p_home, p_draw, p_away = combine_probs(
        elo_home=elo_home,
        elo_draw=elo_draw,
        elo_away=elo_away,
        poisson_home=poisson_pred.p_home,
        poisson_draw=poisson_pred.p_draw,
        poisson_away=poisson_pred.p_away,
    )

    background.add_task(
        analytics.record,
        "predict",
        home=home,
        away=away,
        visitor=visitor_from_request(request),
    )

    return {
        "home": home,
        "away": away,
        "p_home": float(p_home),
        "p_draw": float(p_draw),
        "p_away": float(p_away),
        "r_home": r_home,
        "r_away": r_away,
        "xg_home": float(poisson_pred.xg_home),
        "xg_away": float(poisson_pred.xg_away),
        "top_scorelines": poisson_pred.top_scorelines,
    }


@router.get("/backtest/summary", response_model=BacktestSummaryResponse)
def backtest_summary():
    summary = load_backtest_summary()

    if summary is not None:
        return {
            "matches": int(summary["matches"]),
            "accuracy_1x2": float(summary["accuracy_1x2"]),
            "log_loss": float(summary["log_loss"]),
            "brier_score": float(summary["brier_score"]),
        }

    state = get_state()
    rows = state["pred_rows"]

    if not rows:
        raise HTTPException(
            status_code=400,
            detail="Missing combined_backtest_summary.json and backtest_summary.json. Run the backtests first.",
        )

    acc = accuracy_1x2(rows)
    ll = log_loss_1x2(rows)
    brier = brier_score_1x2(rows)

    return {
        "matches": len(rows),
        "accuracy_1x2": float(acc),
        "log_loss": float(ll),
        "brier_score": float(brier),
    }


@router.get("/model/config")
def model_config():
    state = get_state()
    pred_rows = state["pred_rows"]

    return {
        "model": "combined",
        "elo_weight": ELO_WEIGHT,
        "poisson_weight": 1 - ELO_WEIGHT,
        "start_rating": START_RATING,
        "k": K,
        "home_adv": HOME_ADV,
        "draw_prob": DRAW_PROB,
        "seasons_in_dataset": len(state["seasons"]),
        "seasons": state["seasons"],
        "matches_in_dataset": state["match_count"],
        "matches_backtested": len(pred_rows) if pred_rows else None,
    }


@router.get("/predict/score", response_model=PredictScoreResponse)
def predict_score(
    request: Request,
    background: BackgroundTasks,
    home: str = Query(..., description="Home team name"),
    away: str = Query(..., description="Away team name"),
    max_goals: int = Query(6, ge=0, le=10),
):
    state = get_state()
    home, away = validate_teams(home, away, state["teams"])

    model: PoissonGoalsModel = state["poisson_model"]
    pred = model.predict(home, away, max_goals=max_goals, top_n=5)

    background.add_task(
        analytics.record,
        "predict_score",
        home=home,
        away=away,
        visitor=visitor_from_request(request),
    )

    return {
        "home": pred.home,
        "away": pred.away,
        "xg_home": float(pred.xg_home),
        "xg_away": float(pred.xg_away),
        "p_home": float(pred.p_home),
        "p_draw": float(pred.p_draw),
        "p_away": float(pred.p_away),
        "top_scorelines": pred.top_scorelines,
    }


@router.get("/stats")
def stats():
    try:
        return analytics.summary()
    except Exception:
        return {"enabled": False, "error": "stats unavailable"}
