import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request

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

# ── Caches ───────────────────────────────────────────────────────────────────
_FIXTURES_CACHE: dict = {"data": None, "expires": 0.0}
_PREDICT_CACHE: dict[tuple[str, str], dict] = {}

# Maps football-data.org shortName / name variants → parquet team names
_FD_TEAM_MAP = {
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton": "Brighton",
    "Brighton Hove": "Brighton",
    "Brighton & Hove Albion": "Brighton",
    "Burnley": "Burnley",
    "Chelsea": "Chelsea",
    "Coventry City": "Coventry City",
    "Crystal Palace": "Crystal Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Hull City": "Hull City",
    "Ipswich": "Ipswich",
    "Ipswich Town": "Ipswich",
    "Leeds": "Leeds",
    "Leeds United": "Leeds",
    "Leicester": "Leicester",
    "Leicester City": "Leicester",
    "Liverpool": "Liverpool",
    "Luton": "Luton",
    "Luton Town": "Luton",
    "Man City": "Man City",
    "Man Utd": "Man United",
    "Man United": "Man United",
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Middlesbrough": "Middlesbrough",
    "Newcastle": "Newcastle",
    "Newcastle United": "Newcastle",
    "Nott'm Forest": "Nott'm Forest",
    "Nottingham": "Nott'm Forest",
    "Nottingham Forest": "Nott'm Forest",
    "Sheffield Utd": "Sheffield United",
    "Sheffield United": "Sheffield United",
    "Southampton": "Southampton",
    "Spurs": "Tottenham",
    "Sunderland": "Sunderland",
    "Tottenham": "Tottenham",
    "Tottenham Hotspur": "Tottenham",
    "Watford": "Watford",
    "West Ham": "West Ham",
    "West Ham United": "West Ham",
    "Wolves": "Wolves",
    "Wolverhampton Wanderers": "Wolves",
}

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
            "df": df,
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


def _compute_prediction(home: str, away: str, state: dict) -> dict:
    cache_key = (home, away)
    if cache_key in _PREDICT_CACHE:
        return _PREDICT_CACHE[cache_key]

    r_home = float(state["ratings"].get(home, START_RATING))
    r_away = float(state["ratings"].get(away, START_RATING))

    elo_home, elo_draw, elo_away = predict_proba(
        r_home=r_home, r_away=r_away, home_adv=HOME_ADV, draw_prob=DRAW_PROB,
    )

    model: PoissonGoalsModel = state["poisson_model"]
    poisson_pred = model.predict(home, away, max_goals=6, top_n=5)

    p_home, p_draw, p_away = combine_probs(
        elo_home=elo_home, elo_draw=elo_draw, elo_away=elo_away,
        poisson_home=poisson_pred.p_home, poisson_draw=poisson_pred.p_draw,
        poisson_away=poisson_pred.p_away,
    )

    result = {
        "home": home, "away": away,
        "p_home": float(p_home), "p_draw": float(p_draw), "p_away": float(p_away),
        "r_home": r_home, "r_away": r_away,
        "xg_home": float(poisson_pred.xg_home), "xg_away": float(poisson_pred.xg_away),
        "top_scorelines": poisson_pred.top_scorelines,
    }
    _PREDICT_CACHE[cache_key] = result
    return result


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
    home, away = home.strip(), away.strip()
    if home == away:
        raise HTTPException(status_code=400, detail="home and away must be different teams")

    result = _compute_prediction(home, away, state)
    background.add_task(analytics.record, "predict", home=home, away=away, visitor=visitor_from_request(request))
    return result


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


@router.post("/refresh")
def refresh_data(x_refresh_token: str | None = Header(None)):
    """Fetch the current season's results, rebuild matches.parquet, clear model cache."""
    expected = os.environ.get("REFRESH_SECRET")
    if expected and x_refresh_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Refresh-Token header")

    from src.data.updater import current_season, fetch_season_csv, rebuild_parquet

    season = current_season()
    try:
        _, matches_fetched = fetch_season_csv(season)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch season data: {e}")

    total_rows, data_through = rebuild_parquet()

    if hasattr(get_state, "_cache"):
        del get_state._cache
    _PREDICT_CACHE.clear()

    return {
        "status": "ok",
        "season_updated": f"{season}/{season + 1}",
        "matches_fetched": matches_fetched,
        "total_matches": total_rows,
        "data_through": data_through,
    }


@router.get("/fixtures")
def fixtures():
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY", "")
    if not api_key:
        return {
            "fixtures": [],
            "message": "Set the FOOTBALL_DATA_API_KEY environment variable to load fixtures.",
        }

    now = time.time()

    # Fixtures are always for the upcoming/in-progress season (current calendar year)
    season = datetime.now(timezone.utc).year

    if (
        _FIXTURES_CACHE["data"] is not None
        and _FIXTURES_CACHE["expires"] > now
        and _FIXTURES_CACHE.get("season") == season
    ):
        return _FIXTURES_CACHE["data"]

    url = "https://api.football-data.org/v4/competitions/PL/matches"
    params = {"season": season, "status": "SCHEDULED"}
    headers = {"X-Auth-Token": api_key}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            raw = resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"football-data.org error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch fixtures: {e}")

    state = get_state()
    result_fixtures = []
    for match in raw.get("matches", []):
        home_short = match["homeTeam"].get("shortName") or match["homeTeam"]["name"]
        away_short = match["awayTeam"].get("shortName") or match["awayTeam"]["name"]

        home = _FD_TEAM_MAP.get(home_short, home_short)
        away = _FD_TEAM_MAP.get(away_short, away_short)

        utc_str = match["utcDate"]
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))

        try:
            pred = _compute_prediction(home, away, state)
        except Exception:
            pred = None

        result_fixtures.append({
            "matchday": match.get("matchday", 0),
            "date": dt.strftime("%a %d %b %Y"),
            "time": dt.strftime("%H:%M") + " UTC",
            "utc_date": utc_str,
            "home_team": home,
            "away_team": away,
            "prediction": pred,
        })

    result = {"fixtures": result_fixtures}
    _FIXTURES_CACHE["data"] = result
    _FIXTURES_CACHE["expires"] = now + 3600.0
    _FIXTURES_CACHE["season"] = season
    return result


@router.get("/form")
def team_form(team: str = Query(...), n: int = Query(5, ge=1, le=10)):
    state = get_state()
    if team not in state["teams"]:
        raise HTTPException(status_code=400, detail=f"Unknown team: {team}")

    df: pd.DataFrame = state["df"]
    mask = (df["HomeTeam"] == team) | (df["AwayTeam"] == team)
    recent = df[mask].sort_values("Date").tail(n)

    form = []
    matches_out = []
    for _, row in recent.iterrows():
        is_home = row["HomeTeam"] == team
        gf = int(row["FTHG"]) if is_home else int(row["FTAG"])
        ga = int(row["FTAG"]) if is_home else int(row["FTHG"])
        result = "W" if gf > ga else ("L" if gf < ga else "D")
        form.append(result)
        matches_out.append({
            "date": row["Date"].strftime("%d %b %Y"),
            "home": row["HomeTeam"],
            "away": row["AwayTeam"],
            "home_goals": int(row["FTHG"]),
            "away_goals": int(row["FTAG"]),
            "result": result,
        })

    return {"team": team, "form": form, "matches": matches_out}


@router.get("/h2h")
def head_to_head(
    home: str = Query(...),
    away: str = Query(...),
    n: int = Query(10, ge=1, le=20),
):
    state = get_state()
    home, away = validate_teams(home, away, state["teams"])

    df: pd.DataFrame = state["df"]
    mask = (
        ((df["HomeTeam"] == home) & (df["AwayTeam"] == away))
        | ((df["HomeTeam"] == away) & (df["AwayTeam"] == home))
    )
    h2h = df[mask].sort_values("Date").tail(n)

    home_wins = draws = away_wins = 0
    matches_out = []

    for _, row in h2h.iterrows():
        hg, ag = int(row["FTHG"]), int(row["FTAG"])
        h_team = row["HomeTeam"]
        a_team = row["AwayTeam"]

        if hg > ag:
            winner = h_team
        elif ag > hg:
            winner = a_team
        else:
            winner = None

        if winner == home:
            home_wins += 1
        elif winner == away:
            away_wins += 1
        else:
            draws += 1

        matches_out.append({
            "date": row["Date"].strftime("%d %b %Y"),
            "home": h_team,
            "away": a_team,
            "home_goals": hg,
            "away_goals": ag,
        })

    return {
        "home": home,
        "away": away,
        "home_wins": home_wins,
        "draws": draws,
        "away_wins": away_wins,
        "total": len(matches_out),
        "matches": list(reversed(matches_out)),
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
