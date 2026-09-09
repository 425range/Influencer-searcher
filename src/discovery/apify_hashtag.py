import re
from collections import defaultdict
from apify_client import ApifyClient
from src.models import Candidate

HASHTAG_RE = re.compile(r"(?<!\\w)#([0-9A-Za-z_가-힣]+)")


def _dataset_id(run):
    dataset_id = getattr(run, "default_dataset_id", None)
    if not dataset_id and isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        raise RuntimeError("Could not get Apify dataset id for hashtag discovery.")
    return dataset_id


def _clean_tag(tag):
    return str(tag or "").strip().lstrip("#").strip()


def extract_hashtags(caption: str) -> list[str]:
    return [m.group(1) for m in HASHTAG_RE.finditer(caption or "")]


def discover_by_hashtags(
    client: ApifyClient,
    hashtags: list[str],
    actor_id: str,
    results_limit_per_hashtag: int = 100,
    get_posts: bool = True,
    get_reels: bool = True,
    ad_signal_tags: list[str] | None = None,
):
    hashtags = list(dict.fromkeys(
        _clean_tag(x) for x in (hashtags or []) if _clean_tag(x)
    ))
    if not hashtags:
        print("  hashtag discovery: 0 hashtag")
        return []

    ad_signal_set = {_clean_tag(x).lower() for x in (ad_signal_tags or []) if _clean_tag(x)}
    run_input = {
        "hashtags": hashtags,
        "resultsLimit": int(results_limit_per_hashtag),
        "getPosts": bool(get_posts),
        "getReels": bool(get_reels),
    }
    print(
        f"  hashtag discovery: hashtags={len(hashtags)}, "
        f"limit_per_hashtag={results_limit_per_hashtag}, "
        f"posts={bool(get_posts)}, reels={bool(get_reels)}"
    )
    run = client.actor(actor_id).call(run_input=run_input)
    if run is None:
        raise RuntimeError("Instagram Hashtag Scraper failed.")

    dataset_id = _dataset_id(run)
    agg = defaultdict(lambda: {
        "hashtags": set(),
        "posts": 0,
        "ad_posts": 0,
        "ad_tags": set(),
        "latest_timestamp": "",
    })
    raw_rows = 0

    for item in client.dataset(dataset_id).iterate_items():
        # Ignore actor status/audit rows if an actor emits them.
        username = (
            item.get("owner_username")
            or item.get("ownerUsername")
            or item.get("username")
            or ""
        )
        username = str(username).strip().lstrip("@")
        if not username:
            continue

        raw_rows += 1
        source_tag = _clean_tag(
            item.get("hashtag_scrape")
            or item.get("hashtag")
            or item.get("inputHashtag")
            or item.get("inputUrl")
        )
        caption = str(item.get("caption") or "")
        all_tags = {t.lower() for t in extract_hashtags(caption)}
        matched_ad = sorted(all_tags & ad_signal_set)

        key = username.lower()
        a = agg[key]
        if source_tag:
            a["hashtags"].add(source_tag)
        a["posts"] += 1
        if matched_ad or bool(item.get("isSponsored")) or bool(item.get("is_paid_partnership")):
            a["ad_posts"] += 1
        a["ad_tags"].update(matched_ad)
        ts = str(item.get("timestamp") or "")
        if ts and ts > a["latest_timestamp"]:
            a["latest_timestamp"] = ts

    result = []
    for username_key, a in agg.items():
        username = username_key
        c = Candidate(
            username=username,
            profile_url=f"https://www.instagram.com/{username}/",
            source="hashtag",
            source_seed="",
            discovery_depth=0,
        )
        c.discovery_sources = ["hashtag"]
        c.source_hashtags = sorted(a["hashtags"])
        c.hashtag_discovery_posts = int(a["posts"])
        c.hashtag_ad_posts = int(a["ad_posts"])
        c.hashtag_ad_tags = sorted(a["ad_tags"])
        c.hashtag_ad_ratio = (a["ad_posts"] / a["posts"]) if a["posts"] else 0.0
        c.hashtag_latest_timestamp = a["latest_timestamp"]
        result.append(c)

    print(
        f"  hashtag discovery: raw_media_rows={raw_rows}, "
        f"unique_creators={len(result)}"
    )
    return result
