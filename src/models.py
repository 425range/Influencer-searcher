from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class Candidate:
    username: str
    profile_url: str
    source: str = ""
    source_seed: str = ""
    discovery_depth: int = 0

    display_name: str = ""
    bio: str = ""
    followers: Optional[int] = None
    following: Optional[int] = None
    post_count: Optional[int] = None

    category_scores: Dict[str, float] = field(default_factory=dict)
    seed_similarity: float = 0.0
    score: float = 0.0


@dataclass
class Post:
    username: str
    url: str = ""
    caption: str = ""
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    timestamp: str = ""
    content_type: str = ""
    is_ad: bool = False
