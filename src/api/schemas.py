from pydantic import BaseModel
from typing import List


class HealthResponse(BaseModel):
    status: str


class TeamsResponse(BaseModel):
    teams: List[str]


class Scoreline(BaseModel):
    home_goals: int
    away_goals: int
    prob: float


class PredictResponse(BaseModel):
    home: str
    away: str
    p_home: float
    p_draw: float
    p_away: float
    r_home: float
    r_away: float
    xg_home: float
    xg_away: float
    top_scorelines: List[Scoreline]


class PredictScoreResponse(BaseModel):
    home: str
    away: str
    xg_home: float
    xg_away: float
    p_home: float
    p_draw: float
    p_away: float
    top_scorelines: List[Scoreline]


class BacktestSummaryResponse(BaseModel):
    matches: int
    accuracy_1x2: float
    log_loss: float
    brier_score: float
