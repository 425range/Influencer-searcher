import argparse
import os
from collections import defaultdict

from apify_client import ApifyClient
from dotenv import load_dotenv

from src.config_loader import load_config
from src.models import Candidate
from src.discovery.seed_related import discover_from_seeds
from src.discovery.apify_google import discover_by_keywords
from src.collectors.instagram_profile import scrape_profiles
from src.collectors.profile_parser import enrich_candidate, posts_from_profile
from src.analysis.ad_detector import mark_ads
from src.analysis.category import build_text, category_scores
from src.analysis.metrics import build_metrics
from src.analysis.similarity import seed_similarity
from src.analysis.scoring import final_score
from src.storage.sqlite_store import SQLiteStore
from src.exporters.excel_exporter import export


def merge_candidates(*groups):
    merged = {}

    # Seed-related candidates have priority over keyword candidates.
    priority = {"seed_related": 2, "keyword": 1}

    for group in groups:
        for c in group:
            key = c.username.lower()
            existing = merged.get(key)

            if existing is None:
                merged[key] = c
            elif priority.get(c.source, 0) > priority.get(existing.source, 0):
                merged[key] = c

    return list(merged.values())


def main(config_path):
    load_dotenv()
    cfg = load_config(config_path)

    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN is missing from .env")

    client = ApifyClient(token)

    dcfg = cfg["discovery"]
    filters = cfg["filters"]
    seeds = [x.strip().lstrip("@") for x in dcfg.get("seed_usernames", [])]
    seed_set = {x.lower() for x in seeds}

    print("[1/8] Seed profiles + related profile discovery")
    seed_candidates = discover_from_seeds(
        client=client,
        seed_usernames=seeds,
        depth=dcfg.get("seed_expansion_depth", 1),
        max_related_per_profile=dcfg.get("max_related_per_profile", 20),
        max_candidates=dcfg.get("max_seed_candidates", 100),
    )
    print(f"  seed-related candidates: {len(seed_candidates)}")

    keyword_candidates = []
    if dcfg.get("use_keyword_search", True):
        print("[2/8] Keyword discovery")
        keyword_candidates = discover_by_keywords(
            client=client,
            queries=dcfg.get("queries", []),
            actor_id=dcfg.get("google_actor_id", "apify/google-search-scraper"),
            max_pages_per_query=dcfg.get("max_pages_per_query", 1),
            result_limit=dcfg.get("keyword_result_limit", 50),
        )
        print(f"  keyword candidates: {len(keyword_candidates)}")
    else:
        print("[2/8] Keyword discovery skipped")

    candidates = merge_candidates(seed_candidates, keyword_candidates)
    print(f"  unique candidate pool: {len(candidates)}")

    # Add seeds only to scrape their text; they need not be output candidates.
    all_to_scrape = list(dict.fromkeys(
        [c.username for c in candidates] + seeds
    ))

    print("[3/8] Profile enrichment")
    profile_items = scrape_profiles(client, all_to_scrape)
    item_by_username = {
        str(item.get("username", "")).lower(): item
        for item in profile_items
        if item.get("username")
    }

    posts = []
    enriched = []

    for c in candidates:
        item = item_by_username.get(c.username.lower())
        if not item:
            # No profile data means no follower verification.
            if filters.get("allow_unknown_followers", False):
                enriched.append(c)
            continue

        c = enrich_candidate(c, item)
        posts.extend(posts_from_profile(item))
        enriched.append(c)

    print(f"  profiles enriched: {len(enriched)}")

    print("[4/8] HARD follower filter")
    before = len(enriched)
    candidates = []

    for c in enriched:
        if c.username.lower() in seed_set and not filters.get("include_seed_accounts", False):
            continue

        if c.followers is None:
            if filters.get("allow_unknown_followers", False):
                candidates.append(c)
            continue

        if filters["min_followers"] <= c.followers <= filters["max_followers"]:
            candidates.append(c)

    print(f"  before follower filter: {before}")
    print(f"  after follower filter : {len(candidates)}")

    print("[5/8] Ad detection + metrics")
    posts = mark_ads(posts, cfg["analysis"]["ad_keywords"])
    metrics_by_user = build_metrics(posts)

    posts_by_user = defaultdict(list)
    for p in posts:
        posts_by_user[p.username.lower()].append(p)

    seed_texts = []
    for seed in seeds:
        item = item_by_username.get(seed.lower(), {})
        seed_posts = posts_from_profile(item) if item else []
        seed_texts.append(
            build_text(
                item.get("biography", "") if item else "",
                [p.caption for p in seed_posts]
            )
        )

    print("[6/8] Similarity + category + score")
    for c in candidates:
        user_posts = posts_by_user.get(c.username.lower(), [])
        text = build_text(c.bio, [p.caption for p in user_posts])

        c.category_scores = category_scores(
            text,
            cfg["analysis"]["category_keywords"]
        )
        c.seed_similarity = seed_similarity(c, seed_texts)

        c.score = final_score(
            c,
            metrics_by_user.get(c.username.lower(), {}),
            filters,
            cfg["scoring"]["weights"],
        )

    candidates.sort(key=lambda c: c.score, reverse=True)

    print("[7/8] SQLite")
    store = SQLiteStore(cfg["output"]["sqlite_path"])
    store.save_candidates(candidates)
    store.save_posts(posts)
    store.close()

    print("[8/8] Excel")
    rows = []

    for rank, c in enumerate(candidates, start=1):
        m = metrics_by_user.get(c.username.lower(), {})
        rows.append({
            "rank": rank,
            "username": c.username,
            "profile_url": c.profile_url,
            "source": c.source,
            "source_seed": c.source_seed,
            "discovery_depth": c.discovery_depth,
            "display_name": c.display_name,
            "followers": c.followers,
            "bio": c.bio,
            "seed_similarity": c.seed_similarity,
            "fitness_score": c.category_scores.get("fitness", 0),
            "selfcare_score": c.category_scores.get("selfcare", 0),
            "office_score": c.category_scores.get("office", 0),
            "lifestyle_score": c.category_scores.get("lifestyle", 0),
            "beauty_score": c.category_scores.get("beauty", 0),
            "posts_analyzed": m.get("posts_analyzed", 0),
            "ad_posts": m.get("ad_posts", 0),
            "avg_views": m.get("avg_views", 0),
            "median_views": m.get("median_views", 0),
            "avg_ad_views": m.get("avg_ad_views", 0),
            "avg_organic_views": m.get("avg_organic_views", 0),
            "ad_to_organic_ratio": m.get("ad_to_organic_ratio", 0),
            "engagement_on_views": m.get("engagement_on_views", 0),
            "score": c.score,
        })

    export(rows, cfg["output"]["excel_path"])

    print()
    print("DONE")
    print(f"Candidates: {len(candidates)}")
    print(f"Excel: {cfg['output']['excel_path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/campaign.yaml"
    )
    args = parser.parse_args()
    main(args.config)
