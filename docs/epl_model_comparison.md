# EPL Predictor Model Comparison

## Overview

This document compares the two prediction approaches currently implemented in the EPL Predictor project:

- Elo model
- Poisson model

The goal is to understand how each model performs, what each model is good at, and which model should be used as the main predictor going forward.

---

## 1. Models Compared

### Elo Model
The Elo model assigns each team a rating that changes over time based on match results.

Main ideas:
- every team starts with a base rating
- stronger teams gain rating when they win
- weaker teams lose rating when they lose
- home advantage is included
- output is match outcome probabilities:
  - home win
  - draw
  - away win

Current Elo settings:
- Start rating: 1500
- K-factor: 40
- Home advantage: 65
- Draw probability prior: 0.23

### Poisson Model
The Poisson model predicts the number of goals each team is expected to score.

Main ideas:
- fit a model using historical matches
- estimate expected home goals and away goals
- convert expected goals into scoreline probabilities
- convert scoreline probabilities into:
  - home win
  - draw
  - away win

This model is especially useful for:
- expected goals style outputs
- likely scorelines
- score prediction endpoints

---

## 2. Backtest Setup

### Elo Backtest
The Elo backtest runs through matches in date order.

For each match:
- use current team ratings before the match
- predict home, draw, and away probabilities
- update ratings using the real result

This avoids future data leakage.

### Poisson Backtest
The Poisson backtest uses a rolling training setup.

For each match:
- train the Poisson model only on past matches
- predict the current match
- store probabilities and expected goals

This also avoids future data leakage, but it is slower because the model must be re-fit many times.

---

## 3. Results

### Elo Results
- Matches: 1520
- Accuracy: 0.5408
- Log loss: 0.9776
- Brier score: 0.5813

### Poisson Results
- Matches: 1420
- Accuracy: 0.5310
- Log loss: 1.0067
- Brier score: 0.5954

---

## 4. Metric Meaning

### Accuracy
Measures how often the predicted winner or draw matches the real result.

Higher is better.

### Log Loss
Measures how good the predicted probabilities are.

Lower is better.

This is stronger than accuracy because it punishes overconfident wrong predictions.

### Brier Score
Measures the squared error between predicted probabilities and actual outcomes.

Lower is better.

This helps evaluate how well-calibrated the model is.

---

## 5. Comparison Summary

## Elo vs Poisson

### Accuracy
- Elo: 0.5408
- Poisson: 0.5310

Elo performs better.

### Log Loss
- Elo: 0.9776
- Poisson: 1.0067

Elo performs better.

### Brier Score
- Elo: 0.5813
- Poisson: 0.5954

Elo performs better.

---

## 6. Interpretation

The Elo model is currently the stronger model for predicting 1X2 match outcomes.

Why Elo likely performs better right now:
- it is simpler
- it updates cleanly after every match
- it captures team strength well
- it is less sensitive to data sparsity than the current Poisson setup

The Poisson model is still valuable, even though it performs worse on these outcome metrics.

Why Poisson is still useful:
- it gives expected goals
- it gives scoreline probabilities
- it supports the `/predict/score` endpoint
- it adds more detailed match-level interpretation

So the current conclusion is:

- use Elo as the main model for match outcome prediction
- use Poisson for expected goals and scoreline prediction

---

## 7. Important Note About Match Counts

The two backtests were run on different numbers of matches:

- Elo: 1520 matches
- Poisson: 1420 matches

This is because the Poisson backtest begins after a minimum training window.

That means the comparison is not perfectly apples to apples.

Even so, the current results still show a clear trend:
Elo is stronger on the tested outcome metrics.

---

## 8. Recommended Next Step

The next step is to test a combined model.

### Combined Model Idea
Blend Elo and Poisson probabilities:

- combined_home = w * elo_home + (1 - w) * poisson_home
- combined_draw = w * elo_draw + (1 - w) * poisson_draw
- combined_away = w * elo_away + (1 - w) * poisson_away

Try weights such as:
- 0.5 / 0.5
- 0.6 / 0.4
- 0.7 / 0.3
- 0.8 / 0.2

Then compare the combined model against Elo and Poisson using:
- accuracy
- log loss
- Brier score

---

## 9. Final Conclusion

Current best model for 1X2 prediction:
- Elo

Current best model for scoreline and expected goals output:
- Poisson

Best direction for further improvement:
- test a blended Elo + Poisson model
- compare on the same evaluation range
- choose the final production model based on metrics

---

## 10. Files Produced

### Elo
- `data/processed/elo_predictions.parquet`
- `data/processed/backtest_summary.json`

### Poisson
- `data/processed/poisson_predictions.parquet`
- `data/processed/poisson_backtest_summary.json`
