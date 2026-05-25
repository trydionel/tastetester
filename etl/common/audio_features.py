import requests
import musicbrainzngs as mb

def _prep_mb():
  mb.set_rate_limit()
  mb.set_useragent('trydionel-ds-project', '0.0.1', 'jeff@trydionel.com')


def _reccobeats(path, params):
  headers = {
    'Accept': 'application/json',
    'User-Agent': 'trydionel-ds-project 0.0.1 jeff@trydionel.com'
  }
  res = requests.get(f"https://api.reccobeats.com{path}", headers=headers, params=params)
  return res.json()

def fetch_audio_features(ids: list[str]):
  if (len(ids) > 40):
    raise ValueError(f"Cannot fetch audio features for more than 40 tracks. Given {len(ids)} ids.")

  return _reccobeats("/v1/audio-features", { "ids": ids })

def fetch_track_details(ids: list[str]):
  if (len(ids) > 40):
    raise ValueError(f"Cannot fetch track features for more than 40 tracks. Given {len(ids)} ids.")

  return _reccobeats("/v1/track", { "ids": ids })

def fetch_genres(artist: str):
  _prep_mb()

  res = mb.search_artists(limit=1, artist=artist)
  if len(res['artist-list']) == 0:
    return []

  recordings = res['artist-list'][0]

  if int(recordings['ext:score']) < 95:
    return []
  
  if 'tag-list' not in recordings:
    return []

  tag_list = recordings['tag-list']
  sorted_tags = sorted(tag_list, key=lambda d: int(d['count']), reverse=True)
  return [tag['name'] for tag in sorted_tags[:3]] # top 3 genres reported