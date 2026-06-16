import logging
import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel
from sklearn.model_selection import train_test_split
import xgboost as xgb
import optuna
import numpy as np
import pandas as pd
import requests

from etl.common.audio_features import fetch_audio_features, fetch_genres, fetch_track_details
from etl.common.vectorstore import ListeningVectorStore

try:
    import google.auth
    from google.auth.transport.requests import Request as GoogleAuthRequest
except ImportError:
    google = None
    GoogleAuthRequest = None

class TrackAnalysis(BaseModel):
  details: dict[str, Any]
  matches: list[dict[str, Any]]
  vector: list[float]
  expected_plays: float
  percentile: float

class Recommender():
  def __init__(self, random_state = None, prediction_uri: str | None = None):
    self._store = ListeningVectorStore()
    self._prediction_uri = prediction_uri or os.getenv("TASTETESTER_MODEL_PREDICTION_URI")
  
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
    return self._predict_with_vertex_ai(analysis['vector'])

  def _predict_with_vertex_ai(self, vector):
    if google is None or GoogleAuthRequest is None:
      raise RuntimeError("google-auth is required for Vertex AI prediction")
    if not self._prediction_uri:
      raise RuntimeError("TASTETESTER_MODEL_PREDICTION_URI is not set")

    credentials, _ = google.auth.default()
    if not credentials.valid:
      credentials.refresh(GoogleAuthRequest())

    response = requests.post(
      self._prediction_uri,
      headers={
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
      },
      json={"instances": [vector.tolist() if isinstance(vector, np.ndarray) else vector]},
      timeout=30,
    )
    response.raise_for_status()
    prediction = response.json()
    if "predictions" not in prediction or not prediction["predictions"]:
      raise RuntimeError(f"Unexpected Vertex AI response: {prediction}")

    return float(prediction["predictions"][0][0])