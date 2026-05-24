LISTENING_DB = "etl/artifacts/listening.db"

CONTENT_FEATURES = {
    "numeric": [
        "danceability", "energy", "tempo", "acousticness", "valence",
        "instrumentalness", "liveness", "speechiness", "loudness",
        "total_tracks", "release_date_year",
    ],
    "binary_prefix": "genre:",
    "entity_key": "spotify_track_uri",
    "metadata": [
        "master_metadata_track_name",
        "master_metadata_album_artist_name",
        "master_metadata_album_album_name",
    ],
    "table": "track_content_vectors",
}

BEHAVIORAL_COLS = {
    "total_plays": "total_plays",
    "total_playtime_ms": "total_playtime_ms",
    "years_listened": "years_listened",
    "most_recent_year": "most_recent_year",
    "peak_year": "peak_year",
}

TRACK_DETAILS_COLS = {
    "track_name": "master_metadata_track_name",
    "artist_name": "master_metadata_album_artist_name",
    "album_name": "master_metadata_album_album_name",
    "total_plays": "total_plays",
    "total_playtime_ms": "total_playtime_ms",
    "years_listened": "years_listened",
    "most_recent_year": "most_recent_year",
    "peak_year": "peak_year",
    "danceability": "danceability",
    "energy": "energy",
    "tempo": "tempo",
    "acousticness": "acousticness",
    "valence": "valence",
    "instrumentalness": "instrumentalness",
    "liveness": "liveness",
    "speechiness": "speechiness",
    "loudness": "loudness",
    "total_tracks": "total_tracks",
    "release_date_year": "release_date_year",
}
