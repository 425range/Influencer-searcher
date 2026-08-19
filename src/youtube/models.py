from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class YouTubeChannel:
    channel_name: str
    channel_url: str
    subscribers: Optional[int] = None
    description: str = ""
    source_queries: list[str] = field(default_factory=list)
    category_scores: Dict[str, float] = field(default_factory=dict)
    seed_similarity: float = 0.0
    score: float = 0.0


@dataclass
class YouTubeVideo:
    channel_name: str
    channel_url: str
    video_id: str = ""
    title: str = ""
    url: str = ""
    description: str = ""
    date: str = ""
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    subscribers: Optional[int] = None
    is_ad: bool = False
