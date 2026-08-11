import json
import sqlite3
from pathlib import Path
from src.models import Candidate, Post


SCHEMA = """
CREATE TABLE IF NOT EXISTS influencers (
    username TEXT PRIMARY KEY,
    profile_url TEXT NOT NULL,
    source_query TEXT,
    display_name TEXT,
    bio TEXT,
    followers INTEGER,
    following INTEGER,
    post_count INTEGER,
    category_scores TEXT,
    score REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS posts (
    url TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    caption TEXT,
    views INTEGER,
    likes INTEGER,
    comments INTEGER,
    timestamp TEXT,
    content_type TEXT,
    is_ad INTEGER,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reviews (
    username TEXT PRIMARY KEY,
    review_status TEXT,
    reject_reason TEXT,
    reviewer_note TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class SQLiteStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_candidates(self, candidates: list[Candidate]):
        rows = [
            (
                c.username.lower(),
                c.profile_url,
                c.source_query,
                c.display_name,
                c.bio,
                c.followers,
                c.following,
                c.post_count,
                json.dumps(c.category_scores, ensure_ascii=False),
                c.score,
            )
            for c in candidates
        ]

        self.conn.executemany(
            """
            INSERT INTO influencers (
                username, profile_url, source_query, display_name, bio,
                followers, following, post_count, category_scores, score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                profile_url=excluded.profile_url,
                source_query=excluded.source_query,
                display_name=excluded.display_name,
                bio=excluded.bio,
                followers=excluded.followers,
                following=excluded.following,
                post_count=excluded.post_count,
                category_scores=excluded.category_scores,
                score=excluded.score,
                updated_at=CURRENT_TIMESTAMP
            """,
            rows,
        )
        self.conn.commit()

    def upsert_posts(self, posts: list[Post]):
        rows = []
        for i, p in enumerate(posts):
            synthetic_url = p.url or f"synthetic://{p.username}/{i}"
            rows.append(
                (
                    synthetic_url,
                    p.username.lower(),
                    p.caption,
                    p.views,
                    p.likes,
                    p.comments,
                    p.timestamp,
                    p.content_type,
                    int(p.is_ad),
                )
            )

        self.conn.executemany(
            """
            INSERT INTO posts (
                url, username, caption, views, likes, comments,
                timestamp, content_type, is_ad
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                caption=excluded.caption,
                views=excluded.views,
                likes=excluded.likes,
                comments=excluded.comments,
                timestamp=excluded.timestamp,
                content_type=excluded.content_type,
                is_ad=excluded.is_ad,
                updated_at=CURRENT_TIMESTAMP
            """,
            rows,
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
