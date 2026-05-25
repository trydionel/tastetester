import logging

from etl.common.audio_features import fetch_audio_features, fetch_genres, fetch_track_details
from etl.common.vectorstore import ListeningVectorStore

def recommend(track):
  logging.debug("Loading vector store")
  store = ListeningVectorStore()

  logging.debug(f"Fetching track details for {track}")
  details = fetch_track_details(track)
  logging.debug(f"Got details {details}")

  logging.debug(f"Fetching audio features for {track}")
  features = fetch_audio_features([track])
  if len(features['content']) == 0:
    return None

  audio_features = features['content'][0]
  logging.debug(f"Got features {features}")

  artist = details['content'][0]['artists'][0]['name']
  logging.debug(f"Fetching genres for {artist}")
  genres = fetch_genres(artist)
  logging.debug(f"Got genres {genres}")

  vector = store.build_track_vector(audio_features, genres)
  logging.debug(f"Prepared {vector} for similarity search")

  matches = store.similar_to_vector(vector, limit=5)
  logging.debug(f"Found most similar listening history {matches}")

  logging.debug("Fetching details for similar listening history")
  for match in matches:
    details = store.get_track_details(match['entity_key'])
    print(f"{details['artist_name']} - {details['track_name']} ({details['total_plays']} listens, {match['distance']:.2f} distance)")
  
  return matches