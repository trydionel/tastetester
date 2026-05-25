from prefect import task, flow
from prefect.artifacts import create_link_artifact
import pandas as pd
import json
import glob
import uuid

from etl.common import root_path
from etl.common.persistence import df_to_parquet

def load_listen_data(service):
  out = []
  service_path = root_path().joinpath('data', service) 
  files = glob.glob('*.json', root_dir=service_path)
  for file in files:
    with open(service_path.joinpath(file), 'r') as f:
      out.extend(json.load(f))
  
  return out

@task
def load_spotify_data():
  return load_listen_data('spotify')

@task
def load_lastfm_data():
  def extract_fields(track):
    return {
      'source': 'lastfm',
      'master_metadata_album_artist_name': track['artist']['#text'],
      'master_metadata_album_album_name': track['album']['#text'],
      'master_metadata_track_name': track['name'],
      'ts': pd.to_datetime(int(track['date']['uts']), unit='s', utc=True)
    }

  def flatten_lastfm_data(data):
    out = []
    
    for page in data:
      tracks = page['track']
      out.extend(map(extract_fields, tracks))
    
    return out

  lastfm_data = load_listen_data('lastfm')
  return flatten_lastfm_data(lastfm_data)


@task
def enrich_with_spotify_ids(lastfm_data):
  pass

@task
def build_df_listens(spotify_data, lastfm_data):
  df_spotify = pd.DataFrame.from_dict(spotify_data)
  df_spotify['uuid'] = df_spotify.apply(lambda _: uuid.uuid4(), axis=1).astype(str)
  df_spotify['ts'] = pd.to_datetime(df_spotify['ts'])
  df_spotify['source'] = 'spotify'
  df_spotify = df_spotify.dropna(subset=['spotify_track_uri']) # these represent podcasts, not music

  df_lastfm = pd.DataFrame.from_dict(lastfm_data)
  df_listens = pd.concat([df_spotify, df_lastfm])

  return df_listens.sample(n=250, random_state=42) # Smaller subset for testing

@flow
def construct_listens_history():
  spotify_data = load_spotify_data()
  print(f"Loaded {len(spotify_data)} streams")

  lastfm_data = [] # TODO – get the enrichment sorted out
  df_listens = build_df_listens(spotify_data, lastfm_data)

  parquet_path = str(root_path().joinpath("etl", "artifacts", "listens.parquet"))
  df_to_parquet(df_listens, parquet_path)
  create_link_artifact(link=parquet_path, key="listen-history")

  return parquet_path
