import logging
from pathlib import Path
from typing import Any
from pydantic import BaseModel
from sklearn.model_selection import train_test_split
import xgboost as xgb
import optuna
import numpy as np
import pandas as pd

from etl.common.audio_features import fetch_audio_features, fetch_genres, fetch_track_details
from etl.common.vectorstore import ListeningVectorStore

class TrackAnalysis(BaseModel):
  details: dict[str, Any]
  matches: list[dict[str, Any]]
  vector: list[float]
  expected_plays: float
  percentile: float

class Recommender():
  def __init__(self, random_state = None):
    self._store = ListeningVectorStore()
    self._predicted_listens_model_path = Path(__file__).joinpath("../../etl/artifacts/predicted_listens_model.ubj").resolve()
    self._random_state = random_state or 42
  
  def _predicted_listens_model(self):
    if self._predicted_listens_model_path.exists():
      logging.debug(f"Loading predicted listens model from {self._predicted_listens_model_path}")
      model = xgb.XGBRegressor()
      model.load_model(self._predicted_listens_model_path)
      return model
    
    df_listens = self._store.get_tracks_dataframe()
    X = df_listens[self._store.feature_columns()]
    y = df_listens['total_plays']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=self._random_state)

    def objective(trial):
      pruning_callback = optuna.integration.XGBoostPruningCallback(trial, 'validation_0-poisson-nloglik')
      params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
        "max_depth": trial.suggest_int("max_depth", 6, 12),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1),
        "tree_method": trial.suggest_categorical("tree_method", ["exact", "approx", "hist"]),
        "objective": "count:poisson",
        "eval_metric": "poisson-nloglik",
        "seed": self._random_state,
        "callbacks": [pruning_callback],
        "early_stopping_rounds": 50
      }

      model = xgb.XGBRegressor(**params)
      model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
      results = model.evals_result()
      return np.max(results['validation_0']['poisson-nloglik'])

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=self._random_state))
    study.optimize(objective, n_trials=10)

    model = xgb.XGBRegressor(**study.best_params)
    model.fit(X, y)

    model.save_model(self._predicted_listens_model_path)
    return model
  
  def analyze(self, track) -> TrackAnalysis:
    logging.debug(f"Fetching track details for {track}")
    track_details = fetch_track_details(track)
    if len(track_details['content']) == 0:
      track_details = {}
    else:
      track_details = track_details['content'][0]
    logging.debug(f"Got details {track_details}")

    logging.debug(f"Fetching audio features for {track}")
    features = fetch_audio_features([track])
    if len(features['content']) == 0:
      audio_features = {}
    else:
      audio_features = features['content'][0]
    logging.debug(f"Got features {features}")

    artist = track_details['artists'][0]['name']
    logging.debug(f"Fetching genres for {artist}")
    genres = fetch_genres(artist)
    logging.debug(f"Got genres {genres}")

    vector = self._store.build_track_vector(audio_features, genres)
    logging.debug(f"Prepared {vector} for similarity search")

    matches = self._store.similar_to_vector(vector, limit=5)
    logging.debug(f"Found most similar listening history {matches}")

    logging.debug("Fetching details for similar listening history")
    for match in matches:
      match_details = self._store.get_track_details(match['entity_key'])
      logging.debug(f"{match_details['artist_name']} - {match_details['track_name']} ({match_details['total_plays']} listens, {match['distance']:.2f} distance)")

      match |= dict(match_details)
    
    analysis = { 
      "details": dict(track_details) | { 'genres': genres },
      "vector": vector,
      "matches": matches
    }

    analysis["expected_plays"] = self._predict_listens(analysis)
    analysis["percentile"] = self._store.total_plays_ecdf(analysis["expected_plays"])
    logging.debug(f"Expected number of plays for {analysis['details']['artists'][0]['name']} - {analysis['details']['trackTitle']}: {analysis['expected_plays']:.2f} ({analysis['percentile']:.2f} percentile)")

    return TrackAnalysis(**analysis)

  def _predict_listens(self, analysis):
    model = self._predicted_listens_model()
    input = pd.DataFrame.from_records([analysis['vector']], columns=self._store.feature_columns())
    expected_plays = model.predict(input)

    return float(expected_plays[0])