import argparse
import os
from collections import defaultdict

from dotenv import load_dotenv
from apify_client import ApifyClient

from src.config_loader import load_config
from src.discovery.apify_google import discover_instagram_candidates
from src.collectors.apify_instagram import ApifyInstagramCollector
from src.analysis.ad_detector import mark_ads
from src.analysis.category import category_scores, combined_profile_text
from src.analysis.metrics import build_metrics
from src.analysis.scoring import score_candidate
from src.storage.sqlite_store import SQLiteStore
from src.exporters.excel_exporter import export_candidates


def main(config_path: str):
    load_dotenv()
    config = load_config(config_path)

    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError(
            "APIFY_TOKEN is missing. Copy .env.example to .env and add your token."
        )

    client = ApifyClient(token)

    discovery_cfg = config["discovery"]
    filters = config["filters"]
    analysis_cfg = config["analysis"]
    scoring_cfg = config["scoring"]["weights"]

    print("[1/7] Discovering Instagram candidates...")
    candidates = discover_instagram_candidates(
        client=client,
        queries=discovery_cfg["queries"],
        actor_id=discovery_cfg["google_actor_id"],
        max_pages_per_query=discovery_cfg.get("max_pages_per_query", 1),
        result_limit=discovery_cfg.get("result_limit", 100),
    )
    print(f"  discovered: {len(candidates)}")

    # Seed influencers are always included.
    existing = {c.username.lower() for c in candidates}
    for username in discovery_cfg.get("seed_usernames", []):
        if username.lower() not in existing:
            from src.models import Candidate
            candidates.append(
                Candidate(
                    username=username,
                    profile_url=f"https://www.instagram.com/{username}/",
                    source_query="seed",
                )
            )

    print("[2/7] Collecting profile/post data...")
    collector = ApifyInstagramCollector(client)
    profiles, posts = collector.collect([c.profile_url for c in candidates])

    if not collector.enabled:
        print("  Instagram Actor disabled: discovery-only mode.")
        print("  Set INSTAGRAM_ACTOR_ID in .env to enable profile/post enrichment.")

    # Merge enriched profile data into discovered candidates.
    merged = []
    for c in candidates:
        enriched = profiles.get(c.username.lower())
        if enriched:
            enriched.source_query = c.source_query
            merged.append(enriched)
        else:
            merged.append(c)
    candidates = merged

    print("[3/7] Detecting sponsored posts...")
    posts = mark_ads(posts, analysis_cfg["ad_keywords"])

    print("[4/7] Calculating performance metrics...")
    metrics_by_user = build_metrics(posts)

    posts_by_user = defaultdict(list)
    for p in posts:
        posts_by_user[p.username.lower()].append(p)

    print("[5/7] Category scoring + ranking...")
    final_candidates = []

    for c in candidates:
        user_posts = posts_by_user.get(c.username.lower(), [])
        captions = [p.caption for p in user_posts]
        text = combined_profile_text(c.bio, captions)

        c.category_scores = category_scores(
            text,
            analysis_cfg["category_keywords"],
        )

        metrics = metrics_by_user.get(c.username.lower(), {})
        c.score = score_candidate(
            category_scores=c.category_scores,
            metrics=metrics,
            followers=c.followers,
            filters=filters,
            weights=scoring_cfg,
        )

        # If follower data exists, apply hard range filter.
        if c.followers is not None:
            if not (
                filters["min_followers"]
                <= c.followers
                <= filters["max_followers"]
            ):
                continue

        final_candidates.append(c)

    final_candidates.sort(key=lambda x: x.score, reverse=True)

    print("[6/7] Saving SQLite...")
    store = SQLiteStore(config["output"]["sqlite_path"])
    store.upsert_candidates(final_candidates)
    store.upsert_posts(posts)
    store.close()

    print("[7/7] Exporting Excel...")
    rows = []
    for rank, c in enumerate(final_candidates, start=1):
        m = metrics_by_user.get(c.username.lower(), {})
        rows.append(
            {
                "rank": rank,
                "username": c.username,
                "profile_url": c.profile_url,
                "display_name": c.display_name,
                "followers": c.followers,
                "bio": c.bio,
                "source_query": c.source_query,
                "fitness_score": c.category_scores.get("fitness", 0),
                "selfcare_score": c.category_scores.get("selfcare", 0),
                "office_score": c.category_scores.get("office", 0),
                "beauty_score": c.category_scores.get("beauty", 0),
                "posts_analyzed": m.get("post_count_analyzed", 0),
                "ad_posts": m.get("ad_post_count", 0),
                "avg_views": m.get("avg_views", 0),
                "median_views": m.get("median_views", 0),
                "avg_ad_views": m.get("avg_ad_views", 0),
                "avg_organic_views": m.get("avg_organic_views", 0),
                "ad_to_organic_ratio": m.get("ad_to_organic_view_ratio", 0),
                "engagement_on_views": m.get("engagement_on_views", 0),
                "score": c.score,
            }
        )

    export_candidates(rows, config["output"]["excel_path"])

    print()
    print("Done.")
    print(f"SQLite: {config['output']['sqlite_path']}")
    print(f"Excel : {config['output']['excel_path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/campaign.yaml",
        help="Path to campaign YAML config",
    )
    args = parser.parse_args()
    main(args.config)
