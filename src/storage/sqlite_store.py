import json
import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS influencers (
    username TEXT PRIMARY KEY,
    profile_url TEXT,
    source TEXT,
    source_seed TEXT,
    discovery_depth INTEGER,
    display_name TEXT,
    bio TEXT,
    followers INTEGER,
    following INTEGER,
    post_count INTEGER,
    category_scores TEXT,
    seed_similarity REAL,
    score REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS posts (
    url TEXT PRIMARY KEY,
    username TEXT,
    caption TEXT,
    views INTEGER,
    likes INTEGER,
    comments INTEGER,
    timestamp TEXT,
    content_type TEXT,
    is_ad INTEGER,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class SQLiteStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def save_candidates(self, candidates):
        self.conn.executemany(
            """
            INSERT INTO influencers (
                username, profile_url, source, source_seed, discovery_depth,
                display_name, bio, followers, following, post_count,
                category_scores, seed_similarity, score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                profile_url=excluded.profile_url,
                source=excluded.source,
                source_seed=excluded.source_seed,
                discovery_depth=excluded.discovery_depth,
                display_name=excluded.display_name,
                bio=excluded.bio,
                followers=excluded.followers,
                following=excluded.following,
                post_count=excluded.post_count,
                category_scores=excluded.category_scores,
                seed_similarity=excluded.seed_similarity,
                score=excluded.score,
                updated_at=CURRENT_TIMESTAMP
            """,
            [
                (
                    c.username.lower(), c.profile_url, c.source, c.source_seed,
                    c.discovery_depth, c.display_name, c.bio, c.followers,
                    c.following, c.post_count,
                    json.dumps(c.category_scores, ensure_ascii=False),
                    c.seed_similarity, c.score,
                )
                for c in candidates
            ],
        )
        self.conn.commit()

    def save_posts(self, posts):
        rows = []
        for i, p in enumerate(posts):
            url = p.url or f"synthetic://{p.username}/{i}"
            rows.append((
                url, p.username.lower(), p.caption, p.views, p.likes,
                p.comments, p.timestamp, p.content_type, int(p.is_ad)
            ))

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
