from typing import Iterable
from apify_client import ApifyClient
from src.models import Post

REEL_ACTOR_ID = "apify/instagram-reel-scraper"


def _dataset_id(run):
    dataset_id = getattr(run, "default_dataset_id", None)
    if not dataset_id and isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        raise RuntimeError("Could not get Apify Reel Scraper dataset id.")
    return dataset_id


def _int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def scrape_reels(
    client: ApifyClient,
    usernames: Iterable[str],
    results_limit: int = 30,
    only_posts_newer_than: str | None = None,
    include_shares_count: bool = False,
    skip_pinned_posts: bool = True,
) -> list[dict]:
    usernames = list(dict.fromkeys(
        u.strip().lstrip("@") for u in usernames if u and u.strip()
    ))
    if not usernames:
        return []

    run_input = {
        "username": usernames,
        "resultsLimit": int(results_limit),
        "skipPinnedPosts": bool(skip_pinned_posts),
        "includeSharesCount": bool(include_shares_count),
        "includeTranscript": False,
        "includeDownloadedVideo": False,
    }
    if only_posts_newer_than:
        run_input["onlyPostsNewerThan"] = str(only_posts_newer_than)

    run = client.actor(REEL_ACTOR_ID).call(run_input=run_input)
    if run is None:
        raise RuntimeError("Instagram Reel Scraper failed.")

    return list(client.dataset(_dataset_id(run)).iterate_items())


def reels_from_items(items: list[dict]) -> list[Post]:
    out = []
    for item in items:
        username = item.get("ownerUsername")
        if not username:
            # inputUrl is a fallback only; normal actor output should have ownerUsername.
            metadata = item.get("metaData") or {}
            username = metadata.get("username") or metadata.get("ownerUsername")
        if not username:
            continue

        plays = (
            item.get("videoPlayCount")
            or item.get("igPlayCount")
            or item.get("playCount")
            or item.get("videoViewCount")
        )

        out.append(Post(
            username=str(username),
            url=item.get("url") or "",
            caption=item.get("caption") or "",
            views=_int(plays),
            likes=_int(item.get("likesCount")),
            comments=_int(item.get("commentsCount")),
            shares=_int(item.get("sharesCount") or item.get("reshareCount")),
            timestamp=str(item.get("timestamp") or ""),
            content_type=item.get("productType") or item.get("type") or "Reel",
            paid_partnership=bool(item.get("paidPartnership")),
        ))
    return out
