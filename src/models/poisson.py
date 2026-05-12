from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

FORM_WINDOW = 5
_FORM_COLS = [
    "home_attack_form",
    "home_defence_form",
    "away_attack_form",
    "away_defence_form",
]


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 0.0
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def _rolling_avg(lst: list, window: int) -> float:
    recent = lst[-window:]
    return sum(recent) / len(recent) if recent else 1.0


def compute_rolling_form(df: pd.DataFrame, window: int = FORM_WINDOW) -> pd.DataFrame:
    """
    Add rolling attack/defence form columns to a chronologically sorted match DataFrame.
    Each row's form is derived only from games played before that match (no leakage).
    Teams with no prior history default to 1.0 goals/game.
    """
    df = df.sort_values("Date").reset_index(drop=True)

    scored: defaultdict[str, list] = defaultdict(list)
    conceded: defaultdict[str, list] = defaultdict(list)

    home_atk, home_def, away_atk, away_def = [], [], [], []

    for _, row in df.iterrows():
        h, a = row["HomeTeam"], row["AwayTeam"]

        home_atk.append(_rolling_avg(scored[h], window))
        home_def.append(_rolling_avg(conceded[h], window))
        away_atk.append(_rolling_avg(scored[a], window))
        away_def.append(_rolling_avg(conceded[a], window))

        scored[h].append(int(row["FTHG"]))
        conceded[h].append(int(row["FTAG"]))
        scored[a].append(int(row["FTAG"]))
        conceded[a].append(int(row["FTHG"]))

    df["home_attack_form"] = home_atk
    df["home_defence_form"] = home_def
    df["away_attack_form"] = away_atk
    df["away_defence_form"] = away_def

    return df


def get_team_form(df: pd.DataFrame, team: str, window: int = FORM_WINDOW) -> dict[str, float]:
    """Return a team's current attack/defence form from their last `window` completed matches."""
    mask = (df["HomeTeam"] == team) | (df["AwayTeam"] == team)
    recent = df[mask].sort_values("Date").tail(window)

    goals_scored: list[int] = []
    goals_conceded: list[int] = []

    for _, row in recent.iterrows():
        if row["HomeTeam"] == team:
            goals_scored.append(int(row["FTHG"]))
            goals_conceded.append(int(row["FTAG"]))
        else:
            goals_scored.append(int(row["FTAG"]))
            goals_conceded.append(int(row["FTHG"]))

    return {
        "attack": sum(goals_scored) / len(goals_scored) if goals_scored else 1.0,
        "defence": sum(goals_conceded) / len(goals_conceded) if goals_conceded else 1.0,
    }


@dataclass
class PoissonPrediction:
    home: str
    away: str
    xg_home: float
    xg_away: float
    p_home: float
    p_draw: float
    p_away: float
    top_scorelines: List[Dict[str, object]]


class PoissonGoalsModel:
    """
    Poisson goals model using team identity + rolling attack/defence form.
    Two separate Poisson regressors predict home and away goals.
    Rolling form (last 5 games) is computed from the training data and
    used automatically at inference time — no manual feature passing required.
    """

    def __init__(self, window: int = FORM_WINDOW) -> None:
        self._window = window
        self._home_pipe: Pipeline | None = None
        self._away_pipe: Pipeline | None = None
        self._teams: List[str] = []
        self._df: pd.DataFrame | None = None

    @property
    def teams(self) -> List[str]:
        return self._teams

    def fit(self, df: pd.DataFrame) -> "PoissonGoalsModel":
        needed = {"HomeTeam", "AwayTeam", "FTHG", "FTAG"}
        missing = needed - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        df = compute_rolling_form(df, window=self._window)
        self._df = df
        self._teams = sorted(set(df["HomeTeam"]).union(set(df["AwayTeam"])))

        X = df[["HomeTeam", "AwayTeam"] + _FORM_COLS].copy()
        y_home = df["FTHG"].astype(int).values
        y_away = df["FTAG"].astype(int).values

        pre = ColumnTransformer(
            transformers=[
                ("teams", OneHotEncoder(handle_unknown="ignore"), ["HomeTeam", "AwayTeam"]),
                ("form", "passthrough", _FORM_COLS),
            ],
            remainder="drop",
        )

        self._home_pipe = Pipeline([
            ("pre", pre),
            ("model", PoissonRegressor(alpha=0.0001, max_iter=2000)),
        ])
        self._away_pipe = Pipeline([
            ("pre", pre),
            ("model", PoissonRegressor(alpha=0.0001, max_iter=2000)),
        ])

        self._home_pipe.fit(X, y_home)
        self._away_pipe.fit(X, y_away)

        return self

    def expected_goals(self, home: str, away: str) -> Tuple[float, float]:
        if self._home_pipe is None or self._away_pipe is None or self._df is None:
            raise RuntimeError("Model not fitted. Call fit(df) first.")

        home_form = get_team_form(self._df, home, self._window)
        away_form = get_team_form(self._df, away, self._window)

        X = pd.DataFrame([{
            "HomeTeam": home,
            "AwayTeam": away,
            "home_attack_form": home_form["attack"],
            "home_defence_form": home_form["defence"],
            "away_attack_form": away_form["attack"],
            "away_defence_form": away_form["defence"],
        }])

        xg_home = float(self._home_pipe.predict(X)[0])
        xg_away = float(self._away_pipe.predict(X)[0])

        return max(xg_home, 0.01), max(xg_away, 0.01)

    def predict(
        self,
        home: str,
        away: str,
        max_goals: int = 6,
        top_n: int = 5,
    ) -> PoissonPrediction:
        xg_home, xg_away = self.expected_goals(home, away)

        probs: List[Tuple[int, int, float]] = []
        p_home = 0.0
        p_draw = 0.0
        p_away = 0.0

        for hg in range(0, max_goals + 1):
            p_hg = _poisson_pmf(hg, xg_home)
            for ag in range(0, max_goals + 1):
                p_ag = _poisson_pmf(ag, xg_away)
                p = p_hg * p_ag
                probs.append((hg, ag, p))

                if hg > ag:
                    p_home += p
                elif hg == ag:
                    p_draw += p
                else:
                    p_away += p

        total = p_home + p_draw + p_away
        if total > 0:
            p_home /= total
            p_draw /= total
            p_away /= total

        probs.sort(key=lambda x: x[2], reverse=True)

        top_scorelines: List[Dict[str, object]] = [
            {"home_goals": hg, "away_goals": ag, "prob": float(p / total) if total > 0 else 0.0}
            for hg, ag, p in probs[:top_n]
        ]

        return PoissonPrediction(
            home=home,
            away=away,
            xg_home=xg_home,
            xg_away=xg_away,
            p_home=p_home,
            p_draw=p_draw,
            p_away=p_away,
            top_scorelines=top_scorelines,
        )
