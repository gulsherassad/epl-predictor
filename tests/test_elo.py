from src.models.elo import expected_result, update_ratings, predict_proba


def test_expected_result_equal_ratings_is_half():
    e = expected_result(1500, 1500, home_adv=0)
    assert abs(e - 0.5) < 1e-9


def test_expected_result_home_adv_increases_expectation():
    e_no_adv = expected_result(1500, 1500, home_adv=0)
    e_adv = expected_result(1500, 1500, home_adv=50)
    assert e_adv > e_no_adv


def test_update_ratings_home_win_increases_home_rating():
    r_home_new, r_away_new = update_ratings(
        r_home=1500,
        r_away=1500,
        goals_home=2,
        goals_away=0,
        k=20,
        home_adv=0,
    )
    assert r_home_new > 1500
    assert r_away_new < 1500


def test_update_ratings_draw_moves_ratings_toward_each_other():
    # If home is stronger and it ends in a draw, home should lose points, away should gain
    r_home_new, r_away_new = update_ratings(
        r_home=1600,
        r_away=1400,
        goals_home=1,
        goals_away=1,
        k=20,
        home_adv=0,
    )
    assert r_home_new < 1600
    assert r_away_new > 1400


def test_predict_proba_sums_to_one():
    p_home, p_draw, p_away = predict_proba(1500, 1500, home_adv=0, draw_prob=0.25)
    total = p_home + p_draw + p_away
    assert abs(total - 1.0) < 1e-9


def test_predict_proba_draw_prob_is_respected():
    p_home, p_draw, p_away = predict_proba(1500, 1500, home_adv=0, draw_prob=0.30)
    assert abs(p_draw - 0.30) < 1e-9
