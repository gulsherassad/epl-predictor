from typing import Tuple


def expected_result(r_home: float, r_away: float, home_adv: float = 0.0) -> float:
    diff = (r_home + home_adv) - r_away
    return 1.0 / (1.0 + 10 ** (-diff / 400.0))


def _actual_score(goals_home: int, goals_away: int) -> float:
    if goals_home > goals_away:
        return 1.0
    if goals_home < goals_away:
        return 0.0
    return 0.5


def update_ratings(
    r_home: float,
    r_away: float,
    goals_home: int,
    goals_away: int,
    k: float = 20.0,
    home_adv: float = 0.0,
) -> Tuple[float, float]:
    e_home = expected_result(r_home, r_away, home_adv=home_adv)
    s_home = _actual_score(goals_home, goals_away)

    r_home_new = r_home + k * (s_home - e_home)
    r_away_new = r_away + k * ((1.0 - s_home) - (1.0 - e_home))
    return r_home_new, r_away_new


def predict_proba(
    r_home: float,
    r_away: float,
    home_adv: float = 0.0,
    draw_prob: float = 0.25,
) -> Tuple[float, float, float]:
    if not (0.0 <= draw_prob <= 1.0):
        raise ValueError("draw_prob must be between 0 and 1")

    e_home = expected_result(r_home, r_away, home_adv=home_adv)

    remaining = 1.0 - draw_prob
    p_home = remaining * e_home
    p_draw = draw_prob
    p_away = remaining * (1.0 - e_home)

    return p_home, p_draw, p_away
