from dataclasses import dataclass, field
from typing import Optional, Dict, List


@dataclass
class Candidate:
    username: str
    profile_url: str
    source: str = ""
    source_seed: str = ""
    discovery_depth: int = 0

    # v0.7 graph/reference-set metadata
    reference_hits: List[str] = field(default_factory=list)
    reference_overlap_count: int = 0
    reference_overlap_ratio: float = 0.0
    graph_similarity: Optional[float] = None

    display_name: str = ""
    bio: str = ""
    followers: Optional[int] = None
    following: Optional[int] = None
    post_count: Optional[int] = None

    category_scores: Dict[str, float] = field(default_factory=dict)
    seed_similarity: float = 0.0
    pre_score: float = 0.0

    # Visual
    visual_similarity: Optional[float] = None
    visual_reference_similarity: Optional[float] = None
    visual_post_median_similarity: Optional[float] = None
    nearest_visual_reference: str = ""
    visual_rank: Optional[int] = None
    visual_negative_similarity: Optional[float] = None
    visual_target_margin: Optional[float] = None

    # Text / hashtag
    caption_similarity: Optional[float] = None
    nearest_text_reference: str = ""
    hashtag_similarity: Optional[float] = None
    nearest_hashtag_reference: str = ""
    shared_hashtags: str = ""
    content_similarity: Optional[float] = None
    text_posts_used: int = 0
    topic_similarity: Optional[float] = None
    topic_negative_similarity: Optional[float] = None
    topic_target_margin: Optional[float] = None
    topic_profile: str = ""

    gender_signal: str = ""
    gender_target_match: Optional[bool] = None
    gender_evidence: str = ""
    creator_target_fit: Optional[float] = None
    creator_target_gate: str = ""
    creator_target_reason: str = ""

    # Dynamic reference-set ranking
    combined_similarity: Optional[float] = None
    combined_rank: Optional[int] = None
    ranking_signals_used: str = ""
    quality_pass: Optional[bool] = None

    score: float = 0.0
    status: str = "candidate"
    reject_reason: str = ""


@dataclass
class Post:
    username: str
    url: str = ""
    caption: str = ""
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    timestamp: str = ""
    content_type: str = ""
    is_ad: bool = False
    ad_detection_reason: str = ""
    paid_partnership: bool = False
