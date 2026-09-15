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


def _item_hashtags(item: dict, caption: str) -> set[str]:
    """Prefer Actor-parsed hashtags[] and supplement from caption."""
    tags = set()
    raw = item.get("hashtags") or []
    if isinstance(raw, str):
        # Defensive support for comma/space separated actor variants.
        raw = re.split(r"[,\\s]+", raw)
    if isinstance(raw, (list, tuple, set)):
        for t in raw:
            cleaned = _clean_tag(t)
            if cleaned:
                tags.add(cleaned.lower())
    tags.update(t.lower() for t in extract_hashtags(caption))
    return tags


def discover_by_hashtags(
    client: ApifyClient,
    hashtags: list[str],
    actor_id: str = "dami_studio/instagram-hashtag-scraper",
    results_limit_per_hashtag: int = 100,
    ad_signal_tags: list[str] | None = None,
    return_stats: bool = False,
):
    hashtags = list(dict.fromkeys(
        _clean_tag(x) for x in (hashtags or []) if _clean_tag(x)
    ))
    if not hashtags:
        print("  hashtag discovery: 0 hashtag")
        empty_stats = {
            "dataset_rows": 0,
            "usable_media_rows": 0,
            "rows_with_owner": 0,
            "ad_media_rows": 0,
            "unique_creators": 0,
        }
        return ([], empty_stats) if return_stats else []

    ad_signal_set = {
        _clean_tag(x).lower()
        for x in (ad_signal_tags or [])
        if _clean_tag(x)
    }

    # Dami Studio actor input schema: hashtags + resultsLimit.
    # It returns both image/video/carousel rows; no getPosts/getReels switches.
    run_input = {
        "hashtags": hashtags,
        "resultsLimit": int(results_limit_per_hashtag),
    }

    print(f"  hashtag actor: {actor_id}")
    print(
        f"  hashtag discovery: hashtags={len(hashtags)}, "
        f"results_limit={results_limit_per_hashtag}"
    )
    for idx, tag in enumerate(hashtags, 1):
        print(f"    hashtag {idx}: #{tag}")

    run = client.actor(actor_id).call(run_input=run_input)
    if run is None:
        raise RuntimeError("Instagram Hashtag Scraper failed.")

    dataset_id = _dataset_id(run)
    agg = defaultdict(lambda: {
        "username": "",
        "hashtags": set(),
        "posts": 0,
        "ad_posts": 0,
        "ad_tags": set(),
        "latest_timestamp": "",
    })

    dataset_rows = 0
    usable_media_rows = 0
    rows_with_owner = 0
    ad_media_rows = 0

    for item in client.dataset(dataset_id).iterate_items():
        dataset_rows += 1

        # Dami may emit free diagnostic/sample rows on empty/limited runs.
        if item.get("_sample") or item.get("error") or item.get("errorCode"):
            continue

        username = (
            item.get("ownerUsername")
            or item.get("owner_username")
            or item.get("username")
            or ""
        )
        username = str(username).strip().lstrip("@")
        if not username:
            continue

        rows_with_owner += 1
        usable_media_rows += 1

        source_tag = _clean_tag(
            item.get("hashtag")
            or item.get("hashtag_scrape")
            or item.get("inputHashtag")
        )
        caption = str(item.get("caption") or "")
        all_tags = _item_hashtags(item, caption)
        matched_ad = sorted(all_tags & ad_signal_set)
        is_sponsored = bool(
            item.get("isSponsored")
            or item.get("isPaidPartnership")
            or item.get("is_paid_partnership")
        )

        key = username.lower()
        a = agg[key]
        a["username"] = username
        if source_tag:
            a["hashtags"].add(source_tag)
        a["posts"] += 1

        if matched_ad or is_sponsored:
            a["ad_posts"] += 1
            ad_media_rows += 1
        a["ad_tags"].update(matched_ad)

        ts = str(item.get("timestamp") or "")
        if ts and ts > a["latest_timestamp"]:
            a["latest_timestamp"] = ts

    result = []
    for _, a in agg.items():
        username = a["username"]
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
        c.hashtag_ad_ratio = (
            a["ad_posts"] / a["posts"] if a["posts"] else 0.0
        )
        c.hashtag_latest_timestamp = a["latest_timestamp"]
        result.append(c)

    stats = {
        "dataset_rows": dataset_rows,
        "usable_media_rows": usable_media_rows,
        "rows_with_owner": rows_with_owner,
        "ad_media_rows": ad_media_rows,
        "unique_creators": len(result),
    }
    print(
        "  hashtag discovery result: "
        f"dataset_rows={dataset_rows}, "
        f"usable_media_rows={usable_media_rows}, "
        f"rows_with_owner={rows_with_owner}, "
        f"ad_media_rows={ad_media_rows}, "
        f"unique_creators={len(result)}"
    )
    return (result, stats) if return_stats else result
