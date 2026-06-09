import json
import pickle

try:
    import sqlite3
    # Test if the attribute exists
    getattr(sqlite3.Connection, "enable_load_extension")
except AttributeError:
    # Fall back to sqlean which acts exactly like sqlite3
    import sqlean as sqlite3

import numpy as np
import pandas as pd
import sqlite_vec
from sklearn.preprocessing import StandardScaler

from etl.common.vector_schemas import CONTENT_FEATURES, LISTENING_DB


class ListeningVectorStore:

    def __init__(self, db_path=LISTENING_DB):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self):
        self.conn.execute("DROP TABLE IF EXISTS track_behavior")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS track_details ("
            "  spotify_track_uri TEXT PRIMARY KEY,"
            "  track_name TEXT,"
            "  artist_name TEXT,"
            "  album_name TEXT,"
            "  total_plays INTEGER,"
            "  total_playtime_ms INTEGER,"
            "  years_listened INTEGER,"
            "  most_recent_year INTEGER,"
            "  peak_year REAL,"
            "  danceability REAL, energy REAL, tempo REAL, acousticness REAL,"
            "  valence REAL, instrumentalness REAL, liveness REAL,"
            "  speechiness REAL, loudness REAL,"
            "  genres TEXT,"
            "  total_tracks INTEGER,"
            "  release_date_year INTEGER"
            ")"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS vector_registry ("
            "  subspace TEXT PRIMARY KEY,"
            "  dimensions INTEGER NOT NULL,"
            "  feature_columns TEXT NOT NULL,"
            "  scaler BLOB,"
            "  model_version TEXT DEFAULT 'v1',"
            "  created_at TEXT DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        self.conn.commit()

    def _ensure_content_table(self, expected_dims):
        tables = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'track_content_vectors%'"
        ).fetchall()
        for (t,) in tables:
            self.conn.execute(f'DROP TABLE IF EXISTS "{t}"')
        self.conn.execute(
            f"CREATE VIRTUAL TABLE track_content_vectors USING vec0("
            f"  entity_key TEXT,"
            f"  vector FLOAT[{expected_dims}]"
            f")"
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Track details (denormalized metadata)
    # ------------------------------------------------------------------

    def store_track_details(self, df, col_mapping, entity_key_col):
        genre_cols = [c for c in df.columns if c.startswith("genre:")]
        db_cols = list(col_mapping.keys())
        sql = (
            f"INSERT OR REPLACE INTO track_details(spotify_track_uri, genres, {', '.join(db_cols)}) "
            f"VALUES (?, ?, {', '.join('?' for _ in db_cols)})"
        )

        self.conn.execute("BEGIN TRANSACTION")
        for _, r in df.iterrows():
            genres_list = [c.split(":", 1)[1] for c in genre_cols if r.get(c, 0) == 1]
            genres_json = json.dumps(genres_list)
            vals = [r[entity_key_col], genres_json]
            for df_col in col_mapping.values():
                vals.append(self._safe_val(r.get(df_col)))
            self.conn.execute(sql, tuple(vals))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Content vectors
    # ------------------------------------------------------------------

    def store_content_vectors(self, df, feature_cols, entity_key_col,
                              binary_cols=None):
        available = set(df.columns)
        feature_cols = [c for c in feature_cols if c in available]
        dims = len(feature_cols)
        self._ensure_content_table(dims)
        numeric_cols = [c for c in feature_cols if not (binary_cols and c in binary_cols)]
        scaler, _ = self._load_or_fit_scaler(df, numeric_cols, feature_cols)

        rows = []
        for _, r in df.iterrows():
            numerics = np.array([float(r[c]) for c in numeric_cols], dtype=np.float32)
            scaled_numerics = scaler.transform(numerics.reshape(1, -1)).flatten()

            if binary_cols:
                present = [c for c in binary_cols if c in feature_cols and c in df.columns]
                binaries = np.array([float(r[c]) for c in present], dtype=np.float32)
                vec = np.concatenate([scaled_numerics, binaries])
            else:
                vec = scaled_numerics

            key = r[entity_key_col]
            rows.append((key, sqlite_vec.serialize_float32(vec.tolist())))

        self.conn.execute("BEGIN TRANSACTION")
        for key, vec_bytes in rows:
            self.conn.execute(
                "DELETE FROM track_content_vectors WHERE entity_key = ?", (key,)
            )
            self.conn.execute(
                "INSERT INTO track_content_vectors(entity_key, vector) VALUES (?, ?)",
                (key, vec_bytes),
            )
        self.conn.commit()

    def _load_or_fit_scaler(self, df, numeric_cols, feature_cols):
        row = self.conn.execute(
            "SELECT scaler, feature_columns FROM vector_registry WHERE subspace = 'track_content'"
        ).fetchone()
        if row is not None:
            scaler = pickle.loads(row[0])
            stored_cols = set(json.loads(row[1]))
            current_cols = set(feature_cols)
            if stored_cols == current_cols:
                return scaler, numeric_cols

        scaler = StandardScaler()
        scaler.fit(df[numeric_cols].to_numpy(dtype=float))

        self.conn.execute(
            "INSERT OR REPLACE INTO vector_registry(subspace, dimensions, feature_columns, scaler, model_version) "
            "VALUES ('track_content', ?, ?, ?, 'v1')",
            (len(feature_cols), json.dumps(feature_cols), pickle.dumps(scaler)),
        )
        self.conn.commit()
        return scaler, numeric_cols

    @staticmethod
    def _safe_val(v):
        if v is None:
            return None
        if isinstance(v, float) and np.isnan(v):
            return None
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        return v

            
    def build_track_vector(self, audio_features, genres):
        row = self.conn.execute("SELECT feature_columns, scaler FROM vector_registry WHERE subspace = 'track_content'").fetchone()

        feature_dimensions = json.loads(row[0])
        numeric_features = CONTENT_FEATURES['numeric']
        genre_features = [c for c in feature_dimensions if c not in numeric_features]
        scaler = pickle.loads(row[1])

        audio_vector = scaler.transform([np.asarray([audio_features.get(key, 0) for key in numeric_features], dtype=float)])
        genre_vector = [1 if genre_feature.replace(CONTENT_FEATURES['binary_prefix'], '') in genres else 0 for genre_feature in genre_features]

        return np.concatenate([audio_vector[0], genre_vector]).astype(np.float32)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def feature_columns(self):
        row = self.conn.execute("SELECT feature_columns FROM vector_registry WHERE subspace = 'track_content'").fetchone()
        return json.loads(row[0])

    def similar_to_vector(self, vector, limit=10):
        vec_bytes = sqlite_vec.serialize_float32(
            vector.tolist() if isinstance(vector, np.ndarray) else vector
        )
        rows = self.conn.execute(
            "SELECT entity_key, distance "
            "FROM track_content_vectors "
            "WHERE vector MATCH ? "
            "ORDER BY distance "
            "LIMIT ?",
            (vec_bytes, limit),
        ).fetchall()
        return [{"entity_key": r[0], "distance": r[1]} for r in rows]

    def get_vector_by_key(self, entity_key):
        row = self.conn.execute(
            "SELECT vector FROM track_content_vectors WHERE entity_key = ?", (entity_key,)
        ).fetchone()
        if row is None:
            return None
        return np.frombuffer(row[0], dtype=np.float32)

    def get_track_details(self, spotify_track_uri):
        row = self.conn.execute(
            "SELECT * FROM track_details WHERE spotify_track_uri = ?", (spotify_track_uri,)
        ).fetchone()
        return row

    def get_content_vector_count(self):
        row = self.conn.execute("SELECT COUNT(*) FROM track_content_vectors").fetchone()
        return row[0]

    def get_track_details_count(self):
        row = self.conn.execute("SELECT COUNT(*) FROM track_details").fetchone()
        return row[0]

    def get_tracks_dataframe(self):
        tracks = self.execute("SELECT * FROM track_details").fetchall()
        df_tracks = pd.DataFrame.from_records(tracks, columns=tracks[0].keys(), index="spotify_track_uri")
        df_tracks['genres'] = df_tracks['genres'].apply(lambda x: json.loads(x) or [])
        df_tracks['top_genre'] = df_tracks['genres'].apply(lambda x: x[0] if len(x) > 0 else None) # FIXME: This belongs in the ETL process

        vectors = self.execute("SELECT entity_key, vec_to_json(vector) AS vector FROM track_content_vectors").fetchall()
        keys = self.execute("SELECT feature_columns FROM vector_registry").fetchone()

        def parse_row(row):
            entity_key = row['entity_key']
            vector = json.loads(row['vector'])

            return [entity_key] + vector

        columns = ['entity_key'] + json.loads(keys['feature_columns'])

        df_vectors = pd.DataFrame.from_records(map(parse_row, vectors), columns=columns, index='entity_key')
        df_vectors = df_vectors.dropna()
        df_listens = df_tracks.join(df_vectors.filter(like=CONTENT_FEATURES['binary_prefix']), rsuffix="_").dropna()

        return df_listens

    def execute(self, query):
        return self.conn.execute(query)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
