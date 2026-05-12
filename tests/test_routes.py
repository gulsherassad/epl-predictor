from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_teams():
    response = client.get("/teams")
    assert response.status_code == 200
    data = response.json()
    assert "teams" in data
    assert isinstance(data["teams"], list)
    assert len(data["teams"]) > 0


def test_predict_valid():
    response = client.get("/predict", params={"home": "Arsenal", "away": "Chelsea"})
    assert response.status_code == 200

    data = response.json()
    assert data["home"] == "Arsenal"
    assert data["away"] == "Chelsea"
    assert "p_home" in data
    assert "p_draw" in data
    assert "p_away" in data
    assert "xg_home" in data
    assert "xg_away" in data
    assert "top_scorelines" in data
    assert isinstance(data["top_scorelines"], list)
    assert len(data["top_scorelines"]) > 0

    first = data["top_scorelines"][0]
    assert "home_goals" in first
    assert "away_goals" in first
    assert "prob" in first

    total = data["p_home"] + data["p_draw"] + data["p_away"]
    assert abs(total - 1.0) < 1e-6


def test_predict_same_team():
    response = client.get("/predict", params={"home": "Arsenal", "away": "Arsenal"})
    assert response.status_code == 400
    assert "different teams" in response.json()["detail"]


def test_predict_unknown_team():
    response = client.get("/predict", params={"home": "FakeTeam", "away": "Chelsea"})
    assert response.status_code == 400
    assert "Unknown home team" in response.json()["detail"]


def test_predict_score_valid():
    response = client.get("/predict/score", params={"home": "Arsenal", "away": "Chelsea"})
    assert response.status_code == 200

    data = response.json()
    assert data["home"] == "Arsenal"
    assert data["away"] == "Chelsea"
    assert "xg_home" in data
    assert "xg_away" in data
    assert "top_scorelines" in data
    assert isinstance(data["top_scorelines"], list)


def test_predict_score_same_team():
    response = client.get("/predict/score", params={"home": "Arsenal", "away": "Arsenal"})
    assert response.status_code == 400
    assert "different teams" in response.json()["detail"]

def test_backtest_summary():
    response = client.get("/backtest/summary")
    assert response.status_code == 200

    data = response.json()
    assert "matches" in data
    assert "accuracy_1x2" in data
    assert "log_loss" in data
    assert "brier_score" in data
    assert data["matches"] > 0

def test_model_config():
    response = client.get("/model/config")
    assert response.status_code == 200

    data = response.json()
    assert data["model"] == "combined"
    assert "elo_weight" in data
    assert "poisson_weight" in data
    assert "start_rating" in data
    assert "k" in data
    assert "home_adv" in data
    assert "draw_prob" in data