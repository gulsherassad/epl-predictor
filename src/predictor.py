import json
from math import exp, factorial
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parent / "data" / "team_strengths.json"
MAX_GOALS = 6


def load_model_data() -> tuple[dict[str, dict[str, float]], float, float]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Missing team strengths file: {DATA_PATH}. "
            "Build it first with the build_team_strengths script."
        )

    with DATA_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    teams = data.get("teams")
    meta = data.get("meta", {})

    if not isinstance(teams, dict) or not teams:
        raise ValueError("team_strengths.json is missing a valid 'teams' object")

    base_home_xg = float(meta.get("base_home_xg", 1.45))
    base_away_xg = float(meta.get("base_away_xg", 1.15))

    return teams, base_home_xg, base_away_xg


def poisson_pmf(goals: int, lam: float) -> float:
    return exp(-lam) * (lam ** goals) / factorial(goals)


def clamp_xg(value: float) -> float:
    return max(0.2, min(value, 3.5))


def get_expected_goals(
    home_team: str,
    away_team: str,
    team_strengths: dict[str, dict[str, float]],
    base_home_xg: float,
    base_away_xg: float,
) -> tuple[float, float]:
    if home_team not in team_strengths:
        raise ValueError(f"Unknown home team: {home_team}")

    if away_team not in team_strengths:
        raise ValueError(f"Unknown away team: {away_team}")

    home = team_strengths[home_team]
    away = team_strengths[away_team]

    home_xg = base_home_xg * float(home["attack"]) / float(away["defence"])
    away_xg = base_away_xg * float(away["attack"]) / float(home["defence"])

    return clamp_xg(home_xg), clamp_xg(away_xg)


def build_score_matrix(home_xg: float, away_xg: float) -> list[list[float]]:
    matrix: list[list[float]] = []

    for home_goals in range(MAX_GOALS + 1):
        row: list[float] = []
        for away_goals in range(MAX_GOALS + 1):
            prob = poisson_pmf(home_goals, home_xg) * poisson_pmf(away_goals, away_xg)
            row.append(prob)
        matrix.append(row)

    total = sum(sum(row) for row in matrix)

    if total <= 0:
        raise ValueError("Score matrix total probability is zero")

    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            matrix[i][j] /= total

    return matrix


def get_match_outcome_probs(matrix: list[list[float]]) -> tuple[float, float, float]:
    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for home_goals in range(len(matrix)):
        for away_goals in range(len(matrix[home_goals])):
            prob = matrix[home_goals][away_goals]

            if home_goals > away_goals:
                home_win += prob
            elif home_goals == away_goals:
                draw += prob
            else:
                away_win += prob

    total = home_win + draw + away_win
    if total <= 0:
        raise ValueError("Outcome probabilities sum to zero")

    return home_win, draw, away_win


def get_top_scorelines(matrix: list[list[float]], limit: int = 5) -> list[list[float]]:
    scorelines: list[list[float]] = []

    for home_goals in range(len(matrix)):
        for away_goals in range(len(matrix[home_goals])):
            scorelines.append([home_goals, away_goals, matrix[home_goals][away_goals]])

    scorelines.sort(key=lambda item: item[2], reverse=True)
    return scorelines[:limit]


def predict_match(home_team: str, away_team: str) -> dict[str, Any]:
    if home_team == away_team:
        raise ValueError("Home and away teams must be different")

    team_strengths, base_home_xg, base_away_xg = load_model_data()

    home_xg, away_xg = get_expected_goals(
        home_team,
        away_team,
        team_strengths,
        base_home_xg,
        base_away_xg,
    )

    matrix = build_score_matrix(home_xg, away_xg)
    home_win_prob, draw_prob, away_win_prob = get_match_outcome_probs(matrix)
    top_scorelines = get_top_scorelines(matrix, limit=5)

    total_prob = home_win_prob + draw_prob + away_win_prob

    if not (0.99 <= total_prob <= 1.01):
        raise ValueError(f"Probabilities do not sum correctly: {total_prob}")

    if home_xg < 0 or away_xg < 0:
        raise ValueError("Negative xG detected")

    return {
        "home_win_prob": round(home_win_prob, 4),
        "draw_prob": round(draw_prob, 4),
        "away_win_prob": round(away_win_prob, 4),
        "home_xg": round(home_xg, 2),
        "away_xg": round(away_xg, 2),
        "top_scorelines": [
            [score[0], score[1], round(score[2], 4)]
            for score in top_scorelines
        ],
    }