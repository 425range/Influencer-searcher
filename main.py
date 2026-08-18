import argparse
import os
from collections import defaultdict

from apify_client import ApifyClient
from dotenv import load_dotenv

from src.config_loader import load_config
from src.discovery.seed_related import discover_from_seeds
from src.discovery.apify_google import discover_by_keywords
from src.collectors.instagram_profile import scrape_profiles
from src.collectors.profile_parser import enrich_candidate, posts_from_profile
from src.collectors.instagram_reels import scrape_reels, reels_from_items
from src.analysis.ad_detector import mark_ads
from src.analysis.category import build_text, category_scores
from src.analysis.similarity import seed_similarity
from src.analysis.target_filters import apply_targeting
from src.analysis.scoring import pre_score, final_score
from src.analysis.reel_metrics import build_reel_metrics, commercial_reject_reason
from src.visual.account_ranker import rank_candidates_visual
from src.textual.account_ranker import rank_candidates_text, rank_candidates_combined
from src.storage.sqlite_store import SQLiteStore
from src.exporters.excel_exporter import export


def merge_candidates(*groups):
    merged = {}
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


def reject_row(candidate, reason, stage):
    return {
        "username": candidate.username,
        "profile_url": candidate.profile_url,
        "followers": candidate.followers,
        "source": candidate.source,
        "source_seed": candidate.source_seed,
        "stage": stage,
        "reject_reason": reason,
    }


def candidate_row(c, metrics, performance_analyzed, include_hits="", soft_hits=""):
    return {
        "final_rank": None,
        "combined_rank": c.combined_rank,
        "visual_rank": c.visual_rank,
        "username": c.username,
        "profile_url": c.profile_url,
        "source": c.source,
        "source_seed": c.source_seed,
        "discovery_depth": c.discovery_depth,
        "display_name": c.display_name,
        "followers": c.followers,
        "bio": c.bio,
        "include_keyword_hits": include_hits,
        "soft_exclude_hits": soft_hits,
        "seed_similarity_legacy": c.seed_similarity,
        "pre_score": c.pre_score,
        "visual_similarity": c.visual_similarity,
        "caption_similarity": c.caption_similarity,
        "hashtag_similarity": c.hashtag_similarity,
        "shared_hashtags": c.shared_hashtags,
        "content_similarity": c.content_similarity,
        "text_posts_used": c.text_posts_used,
        "combined_similarity": c.combined_similarity,
        "performance_analyzed": performance_analyzed,
        "reels_scanned": metrics.get("reels_scanned") if performance_analyzed else None,
        "requested_ad_reels": metrics.get("requested_ad_reels") if performance_analyzed else None,
        "found_ad_reels": metrics.get("found_ad_reels") if performance_analyzed else None,
        "ad_reels_sampled": metrics.get("ad_reels_sampled") if performance_analyzed else None,
        "organic_reels_found": metrics.get("organic_reels_found") if performance_analyzed else None,
        "newest_reel_date": metrics.get("newest_reel_date", "") if performance_analyzed else "",
        "oldest_reel_date": metrics.get("oldest_reel_date", "") if performance_analyzed else "",
        "avg_ad_reel_views": metrics.get("avg_ad_reel_views") if performance_analyzed else None,
        "median_ad_reel_views": metrics.get("median_ad_reel_views") if performance_analyzed else None,
        "avg_organic_reel_views": metrics.get("avg_organic_reel_views") if performance_analyzed else None,
        "median_organic_reel_views": metrics.get("median_organic_reel_views") if performance_analyzed else None,
        "ad_view_ratio": metrics.get("ad_view_ratio") if performance_analyzed else None,
        "avg_ad_likes": metrics.get("avg_ad_likes") if performance_analyzed else None,
        "median_ad_likes": metrics.get("median_ad_likes") if performance_analyzed else None,
        "avg_ad_comments": metrics.get("avg_ad_comments") if performance_analyzed else None,
        "median_ad_comments": metrics.get("median_ad_comments") if performance_analyzed else None,
        "avg_ad_shares": metrics.get("avg_ad_shares") if performance_analyzed else None,
        "median_ad_shares": metrics.get("median_ad_shares") if performance_analyzed else None,
        "ad_like_rate": metrics.get("ad_like_rate") if performance_analyzed else None,
        "ad_comment_rate": metrics.get("ad_comment_rate") if performance_analyzed else None,
        "ad_share_rate": metrics.get("ad_share_rate") if performance_analyzed else None,
        "ad_engagement_rate": metrics.get("ad_engagement_rate") if performance_analyzed else None,
        "ad_ratio_in_scanned_reels": metrics.get("ad_ratio_in_scanned_reels") if performance_analyzed else None,
        "final_score": c.score if performance_analyzed else None,
        "review_status": "",
        "reviewer_note": "",
    }


def reel_rows(reels, selected_ad_by_user):
    selected_urls = {
        p.url for xs in selected_ad_by_user.values() for p in xs if p.url
    }
    rows = []
    for p in sorted(reels, key=lambda x: (x.username.lower(), x.timestamp or ""), reverse=True):
        rows.append({
            "username": p.username,
            "upload_date": p.timestamp,
            "reel_url": p.url,
            "is_ad": p.is_ad,
            "selected_for_ad_metric": p.url in selected_urls if p.url else False,
            "ad_detection_reason": p.ad_detection_reason,
            "paid_partnership": p.paid_partnership,
            "views_or_plays": p.views,
            "likes": p.likes,
            "comments": p.comments,
            "shares": p.shares,
            "caption": p.caption,
        })
    return rows


def main(config_path):
    load_dotenv()
    cfg = load_config(config_path)
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN is missing from .env")

    client = ApifyClient(token)
    dcfg = cfg["discovery"]
    filters = cfg["filters"]
    targeting = cfg.get("targeting", {})
    seeds = [x.strip().lstrip("@") for x in dcfg.get("seed_usernames", [])]
    seed_set = {x.lower() for x in seeds}
    rejected_rows = []

    print("[1/11] Candidate discovery")
    seed_candidates = discover_from_seeds(
        client=client,
        seed_usernames=seeds,
        depth=dcfg.get("seed_expansion_depth", 1),
        max_related_per_profile=dcfg.get("max_related_per_profile", 20),
        max_candidates=dcfg.get("max_seed_candidates", 100),
    )
    keyword_candidates = []
    if dcfg.get("use_keyword_search", True):
        keyword_candidates = discover_by_keywords(
            client=client,
            queries=dcfg.get("queries", []),
            actor_id=dcfg.get("google_actor_id", "apify/google-search-scraper"),
            max_pages_per_query=dcfg.get("max_pages_per_query", 1),
            result_limit=dcfg.get("keyword_result_limit", 50),
        )
    candidates = merge_candidates(seed_candidates, keyword_candidates)
    print(f"  unique candidates: {len(candidates)}")

    print("[2/11] Profile enrichment")
    all_to_scrape = list(dict.fromkeys([c.username for c in candidates] + seeds))
    profile_items = scrape_profiles(client, all_to_scrape)
    item_by_username = {
        str(item.get("username", "")).lower(): item
        for item in profile_items if item.get("username")
    }

    profile_posts = []
    enriched = []
    for c in candidates:
        item = item_by_username.get(c.username.lower())
        if not item:
            if filters.get("allow_unknown_followers", False):
                enriched.append(c)
            else:
                rejected_rows.append(reject_row(c, "profile_not_found", "profile"))
            continue
        c = enrich_candidate(c, item)
        user_posts = posts_from_profile(item)
        profile_posts.extend(user_posts)
        enriched.append(c)

    print("[3/11] Hard filters + category")
    # Reuse the already-scraped profile captions for both ad exclusion and text similarity.
    profile_posts = mark_ads(profile_posts, cfg["analysis"]["ad_keywords"])
    profile_posts_by_user = defaultdict(list)
    for p in profile_posts:
        profile_posts_by_user[p.username.lower()].append(p)

    # Seed accounts are not normally kept as candidates, but their captions are
    # still needed to build the reference content vector. Reuse the same
    # Profile Scraper response; no additional Apify call is made.
    for seed in seeds:
        item = item_by_username.get(seed.lower(), {})
        seed_posts = posts_from_profile(item) if item else []
        seed_posts = mark_ads(seed_posts, cfg["analysis"]["ad_keywords"])
        profile_posts_by_user[seed.lower()] = seed_posts

    seed_texts = []
    for seed in seeds:
        item = item_by_username.get(seed.lower(), {})
        ps = posts_from_profile(item) if item else []
        seed_texts.append(build_text(item.get("biography", "") if item else "", [p.caption for p in ps]))

    kept = []
    target_meta = {}
    for c in enriched:
        if c.username.lower() in seed_set and not filters.get("include_seed_accounts", False):
            continue

        if c.followers is None:
            if not filters.get("allow_unknown_followers", False):
                rejected_rows.append(reject_row(c, "unknown_followers", "hard_filter"))
                continue
        elif not (filters["min_followers"] <= c.followers <= filters["max_followers"]):
            rejected_rows.append(reject_row(c, "followers_out_of_range", "hard_filter"))
            continue

        user_posts = profile_posts_by_user.get(c.username.lower(), [])
        text = build_text(c.bio, [p.caption for p in user_posts])
        t = apply_targeting(text, targeting)
        target_meta[c.username.lower()] = t
        if t["hard_reject"]:
            rejected_rows.append(reject_row(c, "hard_exclude:" + ",".join(t["hard_exclude_hits"]), "targeting"))
            continue

        c.category_scores = category_scores(text, cfg["analysis"]["category_keywords"])

        exclude_categories = targeting.get("hard_exclude_categories", [])
        exclude_threshold = float(targeting.get("hard_exclude_category_threshold", 0.20))
        category_rejects = [
            name for name in exclude_categories
            if c.category_scores.get(name, 0.0) >= exclude_threshold
        ]
        if category_rejects:
            rejected_rows.append(reject_row(
                c,
                "hard_exclude_category:" + ",".join(category_rejects),
                "targeting",
            ))
            continue

        c.seed_similarity = seed_similarity(c, seed_texts)
        c.pre_score = pre_score(
            c,
            filters,
            cfg.get("scoring", {}).get("desired_categories", []),
            soft_exclude_hits=len(t["soft_exclude_hits"]),
        )
        kept.append(c)

    candidates = kept
    print(f"  after filters: {len(candidates)}")

    print("[4/11] Caption + hashtag similarity")
    text_cfg = cfg.get("text_similarity", {})
    if text_cfg.get("enabled", True) and candidates:
        candidates = rank_candidates_text(
            candidates=candidates,
            item_by_username=item_by_username,
            posts_by_username=profile_posts_by_user,
            seed_usernames=seeds,
            cfg=text_cfg,
            ad_keywords=cfg["analysis"]["ad_keywords"],
        )
    else:
        print("  text similarity skipped")

    print("[5/11] SigLIP visual similarity")
    if cfg.get("visual", {}).get("enabled", True) and candidates:
        candidates = rank_candidates_visual(candidates, item_by_username, seeds, cfg["visual"])
    else:
        for c in candidates:
            c.visual_similarity = None
            c.visual_rank = None

    print("[6/11] Combined content + visual ranking")
    if candidates:
        candidates = rank_candidates_combined(candidates, cfg.get("similarity_ranking", {}))

    print("[7/11] Select accounts for Reel performance")
    pcfg = cfg.get("performance", {})
    performance_enabled = pcfg.get("enabled", True)
    top_n = int(pcfg.get("accounts_to_analyze", 30))
    perf_candidates = candidates[:top_n] if performance_enabled else []
    perf_usernames = [c.username for c in perf_candidates]
    print(f"  performance targets: {len(perf_usernames)}")

    reels = []
    reel_metrics = {}
    selected_ad_by_user = {}
    if perf_usernames:
        print("[8/11] Reel tab scraping")
        reel_items = scrape_reels(
            client=client,
            usernames=perf_usernames,
            results_limit=int(pcfg.get("max_reels_to_scan", 30)),
            only_posts_newer_than=pcfg.get("only_posts_newer_than") or None,
            include_shares_count=bool(pcfg.get("include_shares_count", False)),
            skip_pinned_posts=bool(pcfg.get("skip_pinned_posts", True)),
        )
        reels = reels_from_items(reel_items)
        reels = mark_ads(reels, cfg["analysis"]["ad_keywords"])
        reel_metrics, selected_ad_by_user = build_reel_metrics(
            reels,
            ad_target=int(pcfg.get("ad_reels_target", 5)),
        )
    else:
        print("[8/11] Reel tab scraping skipped")

    print("[9/11] Commercial filter + final scoring")
    commercial_cfg = cfg.get("commercial_filter", {})
    final_candidates = []
    for c in candidates:
        analyzed = c.username.lower() in {x.lower() for x in perf_usernames}
        metrics = reel_metrics.get(c.username.lower(), {})
        if analyzed:
            reason = commercial_reject_reason(metrics, commercial_cfg)
            if reason:
                rejected_rows.append(reject_row(c, reason, "commercial_filter"))
                continue
            t = target_meta.get(c.username.lower(), {})
            c.score = final_score(
                c,
                metrics,
                filters,
                cfg.get("scoring", {}),
                soft_exclude_hits=len(t.get("soft_exclude_hits", [])),
            )
        final_candidates.append(c)

    # Analyzed candidates first by final score; remaining candidates keep combined similarity order.
    analyzed_names = {x.lower() for x in perf_usernames}
    analyzed = [c for c in final_candidates if c.username.lower() in analyzed_names]
    not_analyzed = [c for c in final_candidates if c.username.lower() not in analyzed_names]
    analyzed.sort(key=lambda c: c.score, reverse=True)
    not_analyzed.sort(key=lambda c: c.combined_rank or 999999)
    final_candidates = analyzed + not_analyzed

    print("[10/11] SQLite")
    store = SQLiteStore(cfg["output"]["sqlite_path"])
    store.save_candidates(final_candidates)
    store.save_posts(profile_posts + reels)
    store.close()

    print("[11/11] Excel")
    candidate_rows = []
    for idx, c in enumerate(final_candidates, start=1):
        t = target_meta.get(c.username.lower(), {})
        analyzed_flag = c.username.lower() in analyzed_names
        row = candidate_row(
            c,
            reel_metrics.get(c.username.lower(), {}),
            analyzed_flag,
            include_hits=", ".join(t.get("include_hits", [])),
            soft_hits=", ".join(t.get("soft_exclude_hits", [])),
        )
        row["final_rank"] = idx if analyzed_flag else None
        candidate_rows.append(row)

    export(
        candidate_rows,
        reel_rows(reels, selected_ad_by_user),
        rejected_rows,
        cfg["output"]["excel_path"],
    )

    print("\nDONE")
    print(f"Candidates kept: {len(final_candidates)}")
    print(f"Rejected: {len(rejected_rows)}")
    print(f"Reels scraped: {len(reels)}")
    print(f"Excel: {cfg['output']['excel_path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/campaign.yaml")
    args = parser.parse_args()
    main(args.config)
