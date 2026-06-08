import logging
from pathlib import Path
from sklearn.model_selection import train_test_split
import xgboost as xgb
import optuna
import numpy as np
import pandas as pd

from etl.common.audio_features import fetch_audio_features, fetch_genres, fetch_track_details
from etl.common.vectorstore import ListeningVectorStore

class Recommender():
  def __init__(self, random_state = None):
    self._store = ListeningVectorStore()
    self._predicted_listens_model_path = Path("models/predicted_listens_model.pkl")
    self._random_state = random_state or 42
  
  def _predicted_listens_model(self):
    if self._predicted_listens_model_path.exists():
      logging.debug(f"Loading predicted listens model from {self._predicted_listens_model_path}")
      model = xgb.XGBRegressor()
      model.load_model(self._predicted_listens_model_path)
      return model
    
    df_listens = self._store.get_tracks_dataframe()

    y = df_listens['total_plays'].copy()
    X = df_listens.drop(columns=['total_plays'])

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
    study.optimize(objective, n_trials=100)

    model = xgb.XGBRegressor(**study.best_params)
    model.fit(X, y)

    model.save_model(self._predicted_listens_model_path)
    return model
  
  def analyze(self, track):
    logging.debug(f"Fetching track details for {track}")
    track_details = fetch_track_details(track)
    # details = {'content': [{'id': '27ff0fda-0e24-45ef-bb95-d08d3c55200b', 'trackTitle': 'The Motherload', 'artists': [{'id': '4e8883d1-2066-4a14-85a4-491206dac463', 'name': 'Mastodon', 'href': 'https://open.spotify.com/artist/1Dvfqq39HxvCJ3GvfeIFuT'}], 'durationMs': 299786, 'isrc': 'USRE11400112', 'ean': None, 'upc': None, 'href': 'https://open.spotify.com/track/6EF0xhfKtQNqUPz2mnE5BD', 'availableCountries': 'AR,AU,AT,BE,BO,BR,BG,CA,CL,CO,CR,CY,CZ,DK,DO,DE,EC,EE,SV,FI,FR,GR,GT,HN,HK,HU,IS,IE,IT,LV,LT,LU,MY,MT,MX,NL,NZ,NI,NO,PA,PY,PE,PH,PL,PT,SG,SK,ES,SE,CH,TW,TR,UY,US,GB,AD,LI,MC,ID,JP,TH,VN,RO,IL,ZA,SA,AE,BH,QA,OM,KW,EG,MA,DZ,TN,LB,JO,PS,IN,BY,KZ,MD,UA,AL,BA,HR,ME,MK,RS,SI,BD,PK,LK,GH,KE,NG,TZ,UG,AG,AM,BS,BB,BZ,BW,BF,CV,CW,DM,FJ,GM,GD,GW,HT,JM,LS,LR,MW,ML,FM,NA,NE,PG,PR,SM,ST,SN,SC,SL,KN,LC,VC,TL,TT,AZ,BN,BI,KH,CM,TD,KM,GQ,SZ,GA,GN,KG,LA,MO,MR,MN,NP,RW,TG,UZ,ZW,BJ,MG,MU,MZ,AO,CI,DJ,ZM,CD,CG,IQ,LY,TJ,VE,ET,XK', 'popularity': 54}]}
    if len(track_details['content']) == 0:
      track_details = {}
    else:
      track_details = track_details['content'][0]
    logging.debug(f"Got details {track_details}")

    logging.debug(f"Fetching audio features for {track}")
    features = fetch_audio_features([track])
    # features = {'content': [{'id': '27ff0fda-0e24-45ef-bb95-d08d3c55200b', 'href': 'https://open.spotify.com/track/6EF0xhfKtQNqUPz2mnE5BD', 'isrc': 'USRE11400112', 'acousticness': 7.1e-06, 'danceability': 0.363, 'energy': 0.971, 'instrumentalness': 0.00358, 'key': 5, 'liveness': 0.0797, 'loudness': -2.974, 'mode': 0, 'speechiness': 0.0776, 'tempo': 146.018, 'valence': 0.347}]}
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
      "details": dict(track_details),
      "vector": vector,
      "matches": matches
    }

    analysis["expected_plays"] = self._predict_listens(analysis)
    logging.debug(f"Expected number of plays for {analysis['details']['artists'][0]['name']} - {analysis['details']['trackTitle']}: {analysis['expected_plays'][0]:.2f}")

    return analysis

  def _predict_listens(self, analysis):
    model = self._predicted_listens_model()
    input = pd.DataFrame.from_records([analysis['vector']], columns=self._store.feature_columns())
    expected_plays = model.predict(input)

    return expected_plays