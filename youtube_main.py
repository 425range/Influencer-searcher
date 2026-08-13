import argparse
import os
from collections import defaultdict

from apify_client import ApifyClient
from dotenv import load_dotenv

from src.config_loader import load_config
from src.youtube.apify_client import YouTubeApify
from src.youtube.discovery import discover_candidate_channels
from src.youtube.parser import enrich_channels_from_videos
from src.youtube.analysis import (
    mark_ads,
    build_channel_text,
    category_scores,
    seed_similarity,
    metrics_by_channel,
)
from src.youtube.scoring import final_score
from src.youtube.storage import YouTubeSQLiteStore
from src.youtube.exporter import export_excel


def main(config_path):
    load_dotenv()
    cfg = load_config(config_path)

    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN is missing from .env")

    ycfg = cfg["youtube"]
    filters = cfg["filters"]
    analysis_cfg = cfg["analysis"]

    client = ApifyClient(token)
    scraper = YouTubeApify(client, ycfg["actor_id"])

    seed_urls = ycfg.get("seed_channel_urls", [])
    seed_url_set = {u.rstrip("/").lower() for u in seed_urls}

    print("[1/8] Scraping seed channels")
    seed_items = scraper.scrape_channels(
        channel_urls=seed_urls,
        max_results=ycfg.get("videos_per_channel", 20),
        max_shorts=ycfg.get("max_results_shorts", 0),
        max_streams=ycfg.get("max_result_streams", 0),
    )

    # Build seed texts grouped by channel URL.
    seed_group = defaultdict(list)
    for item in seed_items:
        channel_url = item.get("channelUrl")
        if channel_url:
            seed_group[str(channel_url).rstrip("/").lower()].append(item)

    seed_texts = []
    for _, items in seed_group.items():
        text_parts = []
        for item in items:
            text_parts.extend([
                str(item.get("channelName") or ""),
                str(item.get("channelDescription") or ""),
                str(item.get("title") or ""),
                str(item.get("text") or ""),
            ])
        seed_texts.append(" ".join(text_parts))

    print(f"  seed channels resolved: {len(seed_group)}")

    print("[2/8] YouTube search discovery")
    candidates = discover_candidate_channels(
        scraper=scraper,
        queries=ycfg.get("search_queries", []),
        per_query=ycfg.get("search_results_per_query", 10),
        max_channels=ycfg.get("max_candidate_channels", 80),
        max_shorts=ycfg.get("max_results_shorts", 0),
        max_streams=ycfg.get("max_result_streams", 0),
    )

    # Seed channels are comparison baselines, not candidates.
    candidates = [
        c for c in candidates
        if c.channel_url.rstrip("/").lower() not in seed_url_set
    ]
    print(f"  candidate channels discovered: {len(candidates)}")

    print("[3/8] Scraping recent videos for candidate channels")
    candidate_items = scraper.scrape_channels(
        channel_urls=[c.channel_url for c in candidates],
        max_results=ycfg.get("videos_per_channel", 20),
        max_shorts=ycfg.get("max_results_shorts", 0),
        max_streams=ycfg.get("max_result_streams", 0),
    )

    candidates, videos = enrich_channels_from_videos(
        candidates,
        candidate_items,
    )

    print(f"  videos collected: {len(videos)}")

    print("[4/8] Hard subscriber filter")
    before = len(candidates)
    filtered = []

    for c in candidates:
        if c.subscribers is None:
            if filters.get("allow_unknown_subscribers", False):
                filtered.append(c)
            continue

        if (
            filters["min_subscribers"]
            <= c.subscribers
            <= filters["max_subscribers"]
        ):
            filtered.append(c)

    candidates = filtered
    allowed_urls = {
        c.channel_url.rstrip("/").lower()
        for c in candidates
    }
    videos = [
        v for v in videos
        if v.channel_url.rstrip("/").lower() in allowed_urls
    ]

    print(f"  before: {before}")
    print(f"  after : {len(candidates)}")

    print("[5/8] Ad detection + performance")
    videos = mark_ads(videos, analysis_cfg["ad_keywords"])
    metrics = metrics_by_channel(videos)

    videos_by_channel = defaultdict(list)
    for v in videos:
        videos_by_channel[v.channel_url.rstrip("/").lower()].append(v)

    print("[6/8] Doctor fit + seed similarity + ranking")
    scored = []

    for c in candidates:
        key = c.channel_url.rstrip("/").lower()
        channel_videos = videos_by_channel.get(key, [])

        text = build_channel_text(c, channel_videos)
        c.category_scores = category_scores(
            text,
            analysis_cfg["category_keywords"],
        )
        c.seed_similarity = seed_similarity(text, seed_texts)

        # Hard medical relevance filter
        doctor_signal = c.category_scores.get("doctor", 0.0)
        if doctor_signal < filters.get("min_doctor_score", 0.0):
            continue

        c.score = final_score(
            c,
            metrics.get(key, {}),
            filters,
            cfg["scoring"]["weights"],
        )
        scored.append(c)

    candidates = sorted(
        scored,
        key=lambda x: x.score,
        reverse=True,
    )

    allowed_urls = {
        c.channel_url.rstrip("/").lower()
        for c in candidates
    }
    videos = [
        v for v in videos
        if v.channel_url.rstrip("/").lower() in allowed_urls
    ]

    print(f"  medically relevant channels: {len(candidates)}")

    print("[7/8] SQLite")
    store = YouTubeSQLiteStore(cfg["output"]["sqlite_path"])
    store.save_channels(candidates)
    store.save_videos(videos)
    store.close()

    print("[8/8] Excel")
    channel_rows = []
    for rank, c in enumerate(candidates, start=1):
        key = c.channel_url.rstrip("/").lower()
        m = metrics.get(key, {})

        channel_rows.append({
            "rank": rank,
            "channel_name": c.channel_name,
            "channel_url": c.channel_url,
            "subscribers": c.subscribers,
            "description": c.description,
            "seed_similarity": c.seed_similarity,
            "doctor_score": c.category_scores.get("doctor", 0),
            "internal_medicine_score": c.category_scores.get(
                "internal_medicine", 0
            ),
            "diet_score": c.category_scores.get("diet", 0),
            "nutrition_score": c.category_scores.get("nutrition", 0),
            "health_score": c.category_scores.get("health", 0),
            "videos_analyzed": m.get("videos_analyzed", 0),
            "ad_videos": m.get("ad_videos", 0),
            "avg_views": m.get("avg_views", 0),
            "median_views": m.get("median_views", 0),
            "avg_ad_views": m.get("avg_ad_views", 0),
            "median_ad_views": m.get("median_ad_views", 0),
            "avg_organic_views": m.get("avg_organic_views", 0),
            "ad_to_organic_ratio": m.get("ad_to_organic_ratio", 0),
            "avg_engagement_on_views": m.get(
                "avg_engagement_on_views", 0
            ),
            "score": c.score,
            "source_queries": " | ".join(c.source_queries),
        })

    video_rows = []
    for v in videos:
        video_rows.append({
            "channel_name": v.channel_name,
            "channel_url": v.channel_url,
            "title": v.title,
            "video_url": v.url,
            "date": v.date,
            "views": v.views,
            "likes": v.likes,
            "comments": v.comments,
            "is_ad": v.is_ad,
            "description": v.description,
        })

    export_excel(
        channel_rows,
        video_rows,
        cfg["output"]["excel_path"],
    )

    print()
    print("DONE")
    print(f"Channels: {len(candidates)}")
    print(f"Videos  : {len(videos)}")
    print(f"Excel   : {cfg['output']['excel_path']}")
    print(f"SQLite  : {cfg['output']['sqlite_path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/doctor_youtube.yaml",
    )
    args = parser.parse_args()
    main(args.config)
