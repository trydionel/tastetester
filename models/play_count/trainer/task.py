from __future__ import annotations
import argparse
import logging
import os
import sys
import pandas as pd
import xgboost as xgb
import numpy as np
import optuna
from sklearn.model_selection import train_test_split

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s\t%(asctime)s\t%(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


def train(train_data_path, model_output_path):
    log.info("Loading training data from %s", train_data_path)
    df_listens = pd.read_parquet(train_data_path)
    log.info("Loaded %d rows, %d columns", len(df_listens), len(df_listens.columns))

    X = df_listens.drop(columns=['total_plays'])
    y = df_listens['total_plays']
    log.info("Features: %s", list(X.columns))

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    log.info("Train/val split: %d / %d rows", len(X_train), len(X_test))

    def objective(trial):
      pruning_callback = optuna.integration.XGBoostPruningCallback(trial, 'validation_0-poisson-nloglik')
      params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
        "max_depth": trial.suggest_int("max_depth", 6, 12),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1),
        "tree_method": trial.suggest_categorical("tree_method", ["exact", "approx", "hist"]),
        "alpha": trial.suggest_float("alpha", 0.0, 1.0),
        "objective": "count:poisson",
        "eval_metric": "poisson-nloglik",
        "callbacks": [pruning_callback],
        "early_stopping_rounds": 50
      }

      model = xgb.XGBRegressor(**params)
      model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
      results = model.evals_result()
      best_score = np.max(results['validation_0']['poisson-nloglik'])
      log.info("Trial %d best score: %.4f — %s", trial.number, best_score, params)
      return best_score

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=10)

    log.info("Best trial: %d — score: %.4f", study.best_trial.number, study.best_value)
    log.info("Best hyperparameters: %s", study.best_params)

    model = xgb.XGBRegressor(**study.best_params)
    log.info("Retraining on full dataset with best params")
    model.fit(X, y, eval_set=[(X, y)], verbose=True)

    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    model.save_model(model_output_path)
    log.info("Model saved to %s", model_output_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--train-data-path', required=True)
    parser.add_argument('--model-output-path', required=True)
    args = parser.parse_args()

    train(args.train_data_path, args.model_output_path)