from src.models import Candidate, Post


def _int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def enrich_candidate(candidate: Candidate, item: dict) -> Candidate:
    candidate.display_name = item.get("fullName") or ""
    candidate.bio = item.get("biography") or ""
    candidate.followers = _int(item.get("followersCount"))
    candidate.following = _int(item.get("followsCount"))
    candidate.post_count = _int(item.get("postsCount"))
    return candidate


def posts_from_profile(item: dict) -> list[Post]:
    username = item.get("username")
    if not username:
        return []

    result = []

    for post in item.get("latestPosts") or []:
        views = (
            post.get("videoViewCount")
            or post.get("videoPlayCount")
            or post.get("playCount")
        )

        result.append(
            Post(
                username=username,
                url=post.get("url") or "",
                caption=post.get("caption") or "",
                views=_int(views),
                likes=_int(post.get("likesCount")),
                comments=_int(post.get("commentsCount")),
                timestamp=str(post.get("timestamp") or ""),
                content_type=post.get("type") or "",
            )
        )

    return result
