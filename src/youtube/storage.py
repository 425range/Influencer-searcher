import json
import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS youtube_channels (
    channel_url TEXT PRIMARY KEY,
    channel_name TEXT,
    subscribers INTEGER,
    description TEXT,
    source_queries TEXT,
    category_scores TEXT,
    seed_similarity REAL,
    score REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS youtube_videos (
    url TEXT PRIMARY KEY,
    channel_url TEXT,
    channel_name TEXT,
    video_id TEXT,
    title TEXT,
    description TEXT,
    date TEXT,
    views INTEGER,
    likes INTEGER,
    comments INTEGER,
    subscribers INTEGER,
    is_ad INTEGER,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class YouTubeSQLiteStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def save_channels(self, channels):
        self.conn.executemany(
            """
            INSERT INTO youtube_channels (
                channel_url, channel_name, subscribers, description,
                source_queries, category_scores, seed_similarity, score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel_url) DO UPDATE SET
                channel_name=excluded.channel_name,
                subscribers=excluded.subscribers,
                description=excluded.description,
                source_queries=excluded.source_queries,
                category_scores=excluded.category_scores,
                seed_similarity=excluded.seed_similarity,
                score=excluded.score,
                updated_at=CURRENT_TIMESTAMP
            """,
            [
                (
                    c.channel_url, c.channel_name, c.subscribers, c.description,
                    json.dumps(c.source_queries, ensure_ascii=False),
                    json.dumps(c.category_scores, ensure_ascii=False),
                    c.seed_similarity, c.score,
                )
                for c in channels
            ],
        )
        self.conn.commit()

    def save_videos(self, videos):
        self.conn.executemany(
            """
            INSERT INTO youtube_videos (
                url, channel_url, channel_name, video_id, title, description,
                date, views, likes, comments, subscribers, is_ad
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title=excluded.title,
                description=excluded.description,
                date=excluded.date,
                views=excluded.views,
                likes=excluded.likes,
                comments=excluded.comments,
                subscribers=excluded.subscribers,
                is_ad=excluded.is_ad,
                updated_at=CURRENT_TIMESTAMP
            """,
            [
                (
                    v.url, v.channel_url, v.channel_name, v.video_id, v.title,
                    v.description, v.date, v.views, v.likes, v.comments,
                    v.subscribers, int(v.is_ad),
                )
                for v in videos if v.url
            ],
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
