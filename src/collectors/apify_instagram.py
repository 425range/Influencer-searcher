import os
from typing import Dict, List, Tuple
from apify_client import ApifyClient

from src.models import Candidate, Post


class ApifyInstagramCollector:
    """
    Generic adapter for an Instagram Actor.

    Important:
    Apify Store Actors do not all share the same input/output schema.
    Configure INSTAGRAM_ACTOR_ID and then adapt:
      1) build_input()
      2) parse_profile()
      3) parse_post()

    The rest of the project does not need to change.
    """

    def __init__(self, client: ApifyClient, actor_id: str | None = None):
        self.client = client
        self.actor_id = actor_id or os.getenv("INSTAGRAM_ACTOR_ID", "")

    @property
    def enabled(self) -> bool:
        return bool(self.actor_id)

    def build_input(self, profile_urls: List[str]) -> dict:
        # Common input pattern used by many profile/post scrapers.
        # Change this method if your selected Actor uses a different field.
        return {
            "directUrls": profile_urls,
            "resultsType": "posts",
            "resultsLimit": 30,
            "searchType": "user",
            "searchLimit": 1,
        }

    def parse_profile(self, item: dict) -> Candidate | None:
        username = (
            item.get("username")
            or item.get("ownerUsername")
            or item.get("userName")
        )
        if not username:
            return None

        followers = (
            item.get("followersCount")
            or item.get("followers")
            or item.get("followerCount")
        )

        return Candidate(
            username=username,
            profile_url=f"https://www.instagram.com/{username}/",
            display_name=item.get("fullName") or item.get("name") or "",
            bio=item.get("biography") or item.get("bio") or "",
            followers=_to_int(followers),
            following=_to_int(item.get("followingCount") or item.get("following")),
            post_count=_to_int(item.get("postsCount") or item.get("postCount")),
        )

    def parse_post(self, item: dict) -> Post | None:
        username = (
            item.get("ownerUsername")
            or item.get("username")
            or item.get("userName")
        )
        if not username:
            return None

        return Post(
            username=username,
            url=item.get("url") or item.get("postUrl") or "",
            caption=item.get("caption") or item.get("text") or "",
            views=_to_int(
                item.get("videoViewCount")
                or item.get("videoPlayCount")
                or item.get("views")
                or item.get("playCount")
            ),
            likes=_to_int(item.get("likesCount") or item.get("likes")),
            comments=_to_int(item.get("commentsCount") or item.get("comments")),
            timestamp=str(
                item.get("timestamp")
                or item.get("takenAt")
                or item.get("date")
                or ""
            ),
            content_type=item.get("type") or item.get("productType") or "",
        )

    def collect(self, profile_urls: List[str]) -> Tuple[Dict[str, Candidate], List[Post]]:
        if not self.enabled:
            return {}, []

        run = self.client.actor(self.actor_id).call(
            run_input=self.build_input(profile_urls)
        )
        if run is None:
            raise RuntimeError("Instagram Actor run failed.")

        dataset_id = getattr(run, "default_dataset_id", None)
        if not dataset_id and isinstance(run, dict):
            dataset_id = run.get("defaultDatasetId")

        profiles: Dict[str, Candidate] = {}
        posts: List[Post] = []

        for item in self.client.dataset(dataset_id).iterate_items():
            profile = self.parse_profile(item)
            if profile:
                profiles[profile.username.lower()] = profile

            post = self.parse_post(item)
            if post:
                posts.append(post)

        return profiles, posts


def _to_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
