import json
import logging
import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel
import numpy as np
import requests

from etl.common.audio_features import fetch_audio_features, fetch_genres, fetch_track_details
from etl.common.vector_schemas import PREDICTION_FEATURES
from etl.common.vectorstore import ListeningVectorStore

try:
    import google.auth
    from google.auth.transport.requests import Request as GoogleAuthRequest
except ImportError:
    google = None
    GoogleAuthRequest = None

try:
    import google.cloud.logging
    client = google.cloud.logging.Client()
    client.setup_logging(log_level=logging.DEBUG)
except Exception:
    logging.info("google-cloud-logging unavailable; logs go to stderr")

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
    self._prediction_features = self._load_prediction_features()
    logging.debug("Recommender initialized with %d prediction features", len(self._prediction_features))

  def _load_prediction_features(self):
    bucket_name = os.environ.get("TASTETESTER_TRAINING_BUCKET")
    if bucket_name:
      try:
        from google.cloud import storage
        client = storage.Client()
        blob = client.bucket(bucket_name).blob("artifacts/prediction_features.json")
        features = json.loads(blob.download_as_bytes())
        local_path = Path(__file__).parent.parent / "etl" / "artifacts" / "prediction_features.json"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "w") as f:
          json.dump(features, f)
        return features
      except Exception:
        logging.warning("GCS fetch failed, falling back to local prediction features")

    path = Path(__file__).parent.parent / "etl" / "artifacts" / "prediction_features.json"
    if path.exists():
      with open(path) as f:
        return json.load(f)
    return list(PREDICTION_FEATURES)
  
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

    # vector = self._store.build_track_vector(audio_features, genres)
    # logging.debug(f"Prepared {vector} for similarity search")

    # matches = self._store.similar_to_vector(vector, limit=5)
    # logging.debug(f"Found most similar listening history {matches}")

    # logging.debug("Fetching details for similar listening history")
    # for match in matches:
    #   match_details = self._store.get_track_details(match['entity_key'])
    #   logging.debug(f"{match_details['artist_name']} - {match_details['track_name']} ({match_details['total_plays']} listens, {match['distance']:.2f} distance)")

    #   match |= dict(match_details)
    
    analysis = {
      "details": dict(track_details) | { 'genres': genres },
      "audio_features": audio_features,
      "vector": [], # vector,
      "matches": [] # matches
    }

    analysis["expected_plays"] = self._predict_listens(analysis)
    analysis["percentile"] = self._store.total_plays_ecdf(analysis["expected_plays"])
    logging.debug(f"Expected number of plays for {analysis['details']['artists'][0]['name']} - {analysis['details']['trackTitle']}: {analysis['expected_plays']:.2f} ({analysis['percentile']:.2f} percentile)")

    return TrackAnalysis(**analysis)

  def _build_prediction_vector(self, analysis):
    audio_features = analysis.get("audio_features", {})
    genres = analysis.get("details", {}).get("genres", []) or []
    genre_set = set(genres)
    vec = []
    for feat in self._prediction_features:
      if feat.startswith("genre:"):
        genre_name = feat.removeprefix("genre:")
        vec.append(1.0 if genre_name in genre_set else 0.0)
      else:
        vec.append(audio_features.get(feat, 0.0))
    return vec

  def _predict_listens(self, analysis):
    return self._predict_with_vertex_ai(self._build_prediction_vector(analysis))

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

    return float(prediction["predictions"][0])