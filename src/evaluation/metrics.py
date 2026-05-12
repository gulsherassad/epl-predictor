import math

OUTCOMES = ("H", "D", "A")


def _clip(p: float, eps: float = 1e-15) -> float:
    if p < eps:
        return eps
    if p > 1.0 - eps:
        return 1.0 - eps
    return p


def accuracy_1x2(rows) -> float:
    correct = 0
    total = 0

    for r in rows:
        probs = {"H": r["p_home"], "D": r["p_draw"], "A": r["p_away"]}
        pred = max(probs, key=probs.get)
        if pred == r["FTR"]:
            correct += 1
        total += 1

    return correct / total if total > 0 else 0.0


def log_loss_1x2(rows, eps: float = 1e-15) -> float:
    total = 0.0
    count = 0

    for r in rows:
        true = r["FTR"]
        probs = {"H": r["p_home"], "D": r["p_draw"], "A": r["p_away"]}
        p_true = _clip(float(probs[true]), eps=eps)
        total += -math.log(p_true)
        count += 1

    return total / count if count > 0 else 0.0


def brier_score_1x2(rows) -> float:
    total = 0.0
    count = 0

    for r in rows:
        true = r["FTR"]
        probs = {"H": float(r["p_home"]), "D": float(r["p_draw"]), "A": float(r["p_away"])}

        y = {"H": 0.0, "D": 0.0, "A": 0.0}
        y[true] = 1.0

        sq = 0.0
        for o in OUTCOMES:
            sq += (probs[o] - y[o]) ** 2

        total += sq
        count += 1

    return total / count if count > 0 else 0.0
