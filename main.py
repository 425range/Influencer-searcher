import argparse
import os
import math
from collections import defaultdict

from apify_client import ApifyClient
from dotenv import load_dotenv

from src.config_loader import load_config
from src.discovery.seed_related import discover_from_seeds
from src.discovery.apify_google import discover_by_keywords
from src.discovery.apify_hashtag import discover_by_hashtags
from src.collectors.instagram_profile import scrape_profiles
from src.collectors.profile_parser import enrich_candidate, posts_from_profile
from src.collectors.instagram_reels import scrape_reels, reels_from_items
from src.analysis.ad_detector import mark_ads
from src.analysis.category import build_text, category_scores
from src.analysis.similarity import seed_similarity
from src.analysis.target_filters import apply_targeting, evaluate_gender_target
from src.analysis.creator_target import evaluate_creator_target
from src.analysis.scoring import pre_score, final_score
from src.analysis.reel_metrics import build_reel_metrics, commercial_reject_reason
from src.visual.account_ranker import rank_candidates_visual
from src.textual.account_ranker import rank_candidates_text, rank_candidates_combined
from src.storage.sqlite_store import SQLiteStore
from src.exporters.excel_exporter import export


def merge_candidates(*groups):
    merged = {}
    priority = {"seed_related": 3, "seed_related_fallback": 3, "hashtag": 2, "keyword": 1}
    for group in groups:
        for c in group:
            key = c.username.lower()
            if not getattr(c, "discovery_sources", None):
                c.discovery_sources = [c.source] if c.source else []
            existing = merged.get(key)
            if existing is None:
                merged[key] = c
                continue

            existing.discovery_sources = sorted(set(existing.discovery_sources) | set(c.discovery_sources))
            existing.source_hashtags = sorted(set(getattr(existing, "source_hashtags", [])) | set(getattr(c, "source_hashtags", [])))
            existing.hashtag_discovery_posts += int(getattr(c, "hashtag_discovery_posts", 0) or 0)
            existing.hashtag_ad_posts += int(getattr(c, "hashtag_ad_posts", 0) or 0)
            existing.hashtag_ad_tags = sorted(set(getattr(existing, "hashtag_ad_tags", [])) | set(getattr(c, "hashtag_ad_tags", [])))
            if existing.hashtag_discovery_posts:
                existing.hashtag_ad_ratio = existing.hashtag_ad_posts / existing.hashtag_discovery_posts
            existing.hashtag_latest_timestamp = max(
                getattr(existing, "hashtag_latest_timestamp", "") or "",
                getattr(c, "hashtag_latest_timestamp", "") or "",
            )

            existing.reference_hits = sorted(set(existing.reference_hits) | set(c.reference_hits))
            existing.reference_overlap_count = max(existing.reference_overlap_count, c.reference_overlap_count, len(existing.reference_hits))
            existing.reference_overlap_ratio = max(existing.reference_overlap_ratio or 0.0, c.reference_overlap_ratio or 0.0)
            if c.graph_similarity is not None:
                existing.graph_similarity = max(existing.graph_similarity or 0.0, c.graph_similarity)
            if priority.get(c.source, 0) > priority.get(existing.source, 0):
                existing.source = c.source
                existing.source_seed = c.source_seed or existing.source_seed
                existing.discovery_depth = c.discovery_depth or existing.discovery_depth
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
        "discovery_sources": ", ".join(c.discovery_sources),
        "source_hashtags": ", ".join(c.source_hashtags),
        "hashtag_discovery_posts": c.hashtag_discovery_posts,
        "hashtag_ad_posts": c.hashtag_ad_posts,
        "hashtag_ad_ratio": c.hashtag_ad_ratio,
        "hashtag_ad_tags": ", ".join(c.hashtag_ad_tags),
        "hashtag_latest_timestamp": c.hashtag_latest_timestamp,
        "source_seed": c.source_seed,
        "discovery_depth": c.discovery_depth,
        "reference_hits": ", ".join(c.reference_hits),
        "reference_overlap_count": c.reference_overlap_count,
        "reference_overlap_ratio": c.reference_overlap_ratio,
        "graph_similarity": c.graph_similarity,
        "display_name": c.display_name,
        "followers": c.followers,
        "follower_in_range": c.follower_in_range,
        "targeting_flag": c.targeting_flag,
        "category_flag": c.category_flag,
        "commercial_flag": c.commercial_flag,
        "bio": c.bio,
        "include_keyword_hits": include_hits,
        "soft_exclude_hits": soft_hits,
        "seed_similarity_legacy": c.seed_similarity,
        "pre_score": c.pre_score,
        "visual_similarity": c.visual_similarity,
        "visual_reference_similarity": c.visual_reference_similarity,
        "visual_post_median_similarity": c.visual_post_median_similarity,
        "nearest_visual_reference": c.nearest_visual_reference,
        "visual_negative_similarity": c.visual_negative_similarity,
        "visual_target_margin": c.visual_target_margin,
        "caption_similarity": c.caption_similarity,
        "nearest_text_reference": c.nearest_text_reference,
        "hashtag_similarity": c.hashtag_similarity,
        "nearest_hashtag_reference": c.nearest_hashtag_reference,
        "shared_hashtags": c.shared_hashtags,
        "content_similarity": c.content_similarity,
        "text_posts_used": c.text_posts_used,
        "topic_similarity": c.topic_similarity,
        "topic_negative_similarity": c.topic_negative_similarity,
        "topic_target_margin": c.topic_target_margin,
        "topic_profile": c.topic_profile,
        "gender_signal": c.gender_signal,
        "gender_target_match": c.gender_target_match,
        "gender_evidence": c.gender_evidence,
        "creator_target_fit": c.creator_target_fit,
        "creator_target_gate": c.creator_target_gate,
        "creator_target_reason": c.creator_target_reason,
        "combined_similarity": c.combined_similarity,
        "ranking_signals_used": c.ranking_signals_used,
        "quality_pass": c.quality_pass,
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



def _profile_followers(item):
    try:
        value = item.get("followersCount") if isinstance(item, dict) else None
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _count_eligible(candidates, item_by_username, filters, seed_set=None):
    seed_set = seed_set or set()
    count = 0
    for c in candidates:
        if c.username.lower() in seed_set:
            continue
        item = item_by_username.get(c.username.lower())
        followers = _profile_followers(item)
        if followers is None:
            continue
        if filters["min_followers"] <= followers <= filters["max_followers"]:
            count += 1
    return count


def _merge_hashtag_rounds(previous, current):
    """Merge adaptive hashtag rounds without double-counting repeated posts.

    A deeper Dami run can include rows already seen in the previous run. Since
    the Actor has no offset parameter, keep the maximum evidence count for an
    account rather than summing repeated rows across runs.
    """
    merged = {c.username.lower(): c for c in (previous or [])}
    for c in current or []:
        key = c.username.lower()
        old = merged.get(key)
        if old is None:
            merged[key] = c
            continue
        old.discovery_sources = sorted(set(old.discovery_sources) | set(c.discovery_sources))
        old.source_hashtags = sorted(set(old.source_hashtags) | set(c.source_hashtags))
        old.hashtag_discovery_posts = max(old.hashtag_discovery_posts, c.hashtag_discovery_posts)
        old.hashtag_ad_posts = max(old.hashtag_ad_posts, c.hashtag_ad_posts)
        old.hashtag_ad_tags = sorted(set(old.hashtag_ad_tags) | set(c.hashtag_ad_tags))
        old.hashtag_ad_ratio = max(old.hashtag_ad_ratio, c.hashtag_ad_ratio)
        old.hashtag_latest_timestamp = max(old.hashtag_latest_timestamp or "", c.hashtag_latest_timestamp or "")
    return list(merged.values())


def _ensure_profile_cache(client, candidates, cache, actor_id, include_latest_posts, billing):
    missing = [
        c.username for c in candidates
        if c.username.lower() not in cache
    ]
    if not missing:
        return
    items = scrape_profiles(
        client,
        missing,
        actor_id=actor_id,
        include_latest_posts=include_latest_posts,
    )
    charged_like_rows = 0
    for item in items:
        username = str(item.get("username", "")).strip()
        if username:
            cache[username.lower()] = item
            charged_like_rows += 1
    billing["profile_rows"] += charged_like_rows


def adaptive_hashtag_discovery(
    client,
    hashtags,
    actor_id,
    ad_signal_tags,
    profile_actor_id,
    profile_include_latest_posts,
    item_by_username,
    seed_candidates,
    seed_set,
    filters,
    target_candidates,
    initial_limit=50,
    growth_factor=2.0,
    max_limit=500,
    max_rounds=4,
    hashtag_cost_per_result=0.0004,
    profile_cost_per_result=0.0007,
    billing=None,
):
    billing = billing if billing is not None else {"hashtag_rows": 0, "profile_rows": 0}
    if not hashtags:
        return [], billing

    related_eligible = _count_eligible(seed_candidates, item_by_username, filters, seed_set)
    if related_eligible >= target_candidates:
        print(
            f"  adaptive hashtag: skipped; follower-fit candidates already "
            f"{related_eligible}/{target_candidates}"
        )
        return [], billing

    cumulative = []
    limit = max(1, int(initial_limit))
    max_limit = max(limit, int(max_limit))
    max_rounds = max(1, int(max_rounds))

    print(
        f"  adaptive hashtag: target={target_candidates}, "
        f"related_follower_fit={related_eligible}, initial_limit={limit}, max_limit={max_limit}"
    )

    for round_idx in range(1, max_rounds + 1):
        round_candidates, stats = discover_by_hashtags(
            client=client,
            hashtags=hashtags,
            actor_id=actor_id,
            results_limit_per_hashtag=limit,
            ad_signal_tags=ad_signal_tags,
            return_stats=True,
        )
        billing["hashtag_rows"] += int(stats.get("usable_media_rows", 0) or 0)
        cumulative = _merge_hashtag_rounds(cumulative, round_candidates)

        all_for_profile = merge_candidates(seed_candidates, cumulative)
        _ensure_profile_cache(
            client,
            all_for_profile,
            item_by_username,
            profile_actor_id,
            profile_include_latest_posts,
            billing,
        )
        eligible = _count_eligible(all_for_profile, item_by_username, filters, seed_set)
        est_cost = (
            billing["hashtag_rows"] * hashtag_cost_per_result
            + billing["profile_rows"] * profile_cost_per_result
        )
        print(
            f"  adaptive hashtag round {round_idx}: limit={limit}, "
            f"hashtag_creators={len(cumulative)}, merged={len(all_for_profile)}, "
            f"follower_fit={eligible}/{target_candidates}, "
            f"estimated_discovery_cost=${est_cost:.3f}"
        )

        if eligible >= target_candidates:
            print("  adaptive hashtag: target reached")
            break
        if limit >= max_limit:
            print("  adaptive hashtag: max search limit reached")
            break

        next_limit = int(math.ceil(limit * float(growth_factor)))
        if next_limit <= limit:
            next_limit = limit + 50
        limit = min(max_limit, next_limit)

    return cumulative, billing

def main(config_path):
    load_dotenv()
    cfg = load_config(config_path)
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN is missing from .env")

    client = ApifyClient(token)
    dcfg = cfg["discovery"]
    profile_actor_id = dcfg.get("profile_actor_id", "dami_studio/instagram-profile-scraper")
    profile_include_latest_posts = bool(dcfg.get("profile_include_latest_posts", True))
    filters = cfg["filters"]
    targeting = cfg.get("targeting", {})
    seeds = [x.strip().lstrip("@") for x in dcfg.get("seed_usernames", [])]
    seed_set = {x.lower() for x in seeds}
    negative_refs = [
        x.strip().lstrip("@")
        for x in cfg.get("reference_matching", {}).get("negative_usernames", [])
        if str(x).strip()
    ]
    negative_ref_set = {x.lower() for x in negative_refs}
    rejected_rows = []
    print(f"  references: positive={len(seeds)}, negative={len(negative_refs)}")

    print("[1/12] Candidate discovery")
    discovery_profile_cache = {}
    billing = {"hashtag_rows": 0, "profile_rows": 0}

    target_candidates = max(1, int(dcfg.get("target_candidates", 100)))
    has_hashtags = bool([x for x in dcfg.get("hashtags", []) if str(x).strip()])
    has_seeds = bool(seeds)

    # Minimal-GUI strategy: when both sources are present, Related is capped to
    # a conservative share so it cannot consume the whole target by itself.
    # Hashtag discovery then adaptively fills the remaining follower-fit target.
    related_share = float(dcfg.get("related_share_when_both", 0.30))
    if has_seeds and has_hashtags:
        related_target_cap = max(1, int(math.ceil(target_candidates * related_share)))
    else:
        related_target_cap = target_candidates

    seed_candidates = []
    if has_seeds:
        print(
            f"  related discovery: ENABLED (hidden depth={dcfg.get('seed_expansion_depth', 2)}, "
            f"max_candidates={related_target_cap})"
        )
        seed_candidates = discover_from_seeds(
            client=client,
            seed_usernames=seeds,
            depth=dcfg.get("seed_expansion_depth", 2),
            max_related_per_profile=dcfg.get("max_related_per_profile", 20),
            max_candidates=related_target_cap,
            profile_cache=discovery_profile_cache,
            use_related_fallback=dcfg.get("use_related_fallback", True),
            related_fallback_actor_id=dcfg.get(
                "related_fallback_actor_id",
                "instagram-scraper/instagram-related-profiles",
            ),
            profile_actor_id=profile_actor_id,
        )
        # Follower-fit count is needed before deciding how much hashtag search
        # is necessary. Candidate profiles are cheap and cached for enrichment.
        _ensure_profile_cache(
            client,
            seed_candidates,
            discovery_profile_cache,
            profile_actor_id,
            profile_include_latest_posts,
            billing,
        )
    else:
        print("  related discovery: skipped (no reference accounts)")

    hashtag_candidates = []
    if has_hashtags:
        hashtag_candidates, billing = adaptive_hashtag_discovery(
            client=client,
            hashtags=dcfg.get("hashtags", []),
            actor_id=dcfg.get("hashtag_actor_id", "dami_studio/instagram-hashtag-scraper"),
            ad_signal_tags=dcfg.get("hashtag_ad_signal_tags", cfg["analysis"].get("ad_keywords", [])),
            profile_actor_id=profile_actor_id,
            profile_include_latest_posts=profile_include_latest_posts,
            item_by_username=discovery_profile_cache,
            seed_candidates=seed_candidates,
            seed_set=seed_set,
            filters=filters,
            target_candidates=target_candidates,
            initial_limit=int(dcfg.get("hashtag_initial_results_limit", 50)),
            growth_factor=float(dcfg.get("hashtag_growth_factor", 2.0)),
            max_limit=int(dcfg.get("hashtag_max_results_limit", 500)),
            max_rounds=int(dcfg.get("hashtag_max_rounds", 4)),
            hashtag_cost_per_result=float(dcfg.get("hashtag_cost_per_result_usd", 0.0004)),
            profile_cost_per_result=float(dcfg.get("profile_cost_per_result_usd", 0.0007)),
            billing=billing,
        )
    else:
        print("  hashtag discovery: skipped (no hashtags)")

    keyword_candidates = []
    if dcfg.get("use_keyword_search", False):
        keyword_candidates = discover_by_keywords(
            client=client,
            queries=dcfg.get("queries", []),
            actor_id=dcfg.get("google_actor_id", "apify/google-search-scraper"),
            max_pages_per_query=dcfg.get("max_pages_per_query", 1),
            result_limit=dcfg.get("keyword_result_limit", 50),
        )

    candidates = merge_candidates(seed_candidates, hashtag_candidates, keyword_candidates)
    follower_fit_discovery = _count_eligible(candidates, discovery_profile_cache, filters, seed_set)
    estimated_discovery_cost = (
        billing["hashtag_rows"] * float(dcfg.get("hashtag_cost_per_result_usd", 0.0004))
        + billing["profile_rows"] * float(dcfg.get("profile_cost_per_result_usd", 0.0007))
    )
    print(
        f"  discovery summary: related={len(seed_candidates)}, "
        f"hashtag={len(hashtag_candidates)}, google={len(keyword_candidates)}, "
        f"merged_unique={len(candidates)}, follower_fit={follower_fit_discovery}/{target_candidates}"
    )
    print(
        f"  discovery billing estimate: hashtag_rows={billing['hashtag_rows']}, "
        f"profile_rows={billing['profile_rows']}, estimated=${estimated_discovery_cost:.3f} "
        "(Related Actor cost not included)"
    )

    print("[2/12] Profile enrichment")
    all_needed = list(dict.fromkeys(
        [c.username for c in candidates] + seeds + negative_refs
    ))

    # Start with profiles already scraped during seed discovery.
    item_by_username = dict(discovery_profile_cache)
    missing_profiles = [
        username for username in all_needed
        if username.lower() not in item_by_username
    ]

    if missing_profiles:
        print(
            f"  profile enrichment: cached={len(item_by_username)}, "
            f"scraping_missing={len(missing_profiles)}"
        )
        profile_items = scrape_profiles(
            client, missing_profiles,
            actor_id=profile_actor_id,
            include_latest_posts=profile_include_latest_posts,
        )
        for item in profile_items:
            username = str(item.get("username", "")).strip()
            if username:
                item_by_username[username.lower()] = item
    else:
        print(
            f"  profile enrichment: cached={len(item_by_username)}, "
            "scraping_missing=0"
        )

    if not candidates:
        print(
            "  WARNING: discovery returned 0 candidates. "
            "No extra candidate profile requests will be made."
        )

    profile_posts = []
    enriched = []
    unavailable_candidates = []
    for c in candidates:
        item = item_by_username.get(c.username.lower())
        if not item:
            c.status = "profile_unavailable"
            c.targeting_flag = "profile_not_found"
            unavailable_candidates.append(c)
            continue
        c = enrich_candidate(c, item)
        user_posts = posts_from_profile(item)
        profile_posts.extend(user_posts)
        enriched.append(c)

    print("[3/12] Candidate signals + category")
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

    for ref in negative_refs:
        item = item_by_username.get(ref.lower(), {})
        ref_posts = posts_from_profile(item) if item else []
        ref_posts = mark_ads(ref_posts, cfg["analysis"]["ad_keywords"])
        profile_posts_by_user[ref.lower()] = ref_posts

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
        if c.username.lower() in negative_ref_set:
            # Negative references are controls, not discovery candidates.
            continue

        if c.followers is None:
            c.follower_in_range = None
        else:
            c.follower_in_range = bool(filters["min_followers"] <= c.followers <= filters["max_followers"])

        user_posts = profile_posts_by_user.get(c.username.lower(), [])
        text = build_text(c.bio, [p.caption for p in user_posts])
        t = apply_targeting(text, targeting)

        # Conservative creator gender-target filter. Uses explicit Bio/Caption
        # self-description signals only; no image/name-based inference.
        gender_meta = evaluate_gender_target(
            bio=c.bio,
            captions=[p.caption for p in user_posts],
            gender_cfg=targeting.get("gender_filter", {}),
        )
        t.update(gender_meta)
        target_meta[c.username.lower()] = t

        c.gender_signal = gender_meta["gender_signal"]
        c.gender_target_match = gender_meta["gender_target_match"]
        c.gender_evidence = gender_meta["gender_evidence"]

        flags = []
        if t["hard_reject"]:
            flags.append("hard_exclude:" + ",".join(t["hard_exclude_hits"]))
        if gender_meta["gender_reject"]:
            flags.append("gender_target_mismatch:" + gender_meta["gender_signal"])
        c.targeting_flag = " | ".join(flags)

        c.category_scores = category_scores(text, cfg["analysis"]["category_keywords"])

        exclude_categories = targeting.get("hard_exclude_categories", [])
        exclude_threshold = float(targeting.get("hard_exclude_category_threshold", 0.20))
        category_rejects = [
            name for name in exclude_categories
            if c.category_scores.get(name, 0.0) >= exclude_threshold
        ]
        if category_rejects:
            c.category_flag = "hard_exclude_category:" + ",".join(category_rejects)

        c.seed_similarity = seed_similarity(c, seed_texts)
        c.pre_score = pre_score(
            c,
            filters,
            cfg.get("scoring", {}).get("desired_categories", []),
            soft_exclude_hits=len(t["soft_exclude_hits"]),
        )
        kept.append(c)

    candidates = kept
    print(f"  candidates retained (no reject): {len(candidates)}")

    print("[4/12] Caption + hashtag similarity")
    text_cfg = cfg.get("text_similarity", {})
    if text_cfg.get("enabled", True) and candidates:
        candidates = rank_candidates_text(
            candidates=candidates,
            item_by_username=item_by_username,
            posts_by_username=profile_posts_by_user,
            seed_usernames=seeds,
            cfg=text_cfg,
            ad_keywords=cfg["analysis"]["ad_keywords"],
            reference_cfg=cfg.get("reference_matching", {}),
            negative_usernames=negative_refs,
        )
    else:
        print("  text similarity skipped")

    print("[5/12] SigLIP visual similarity")
    if cfg.get("visual", {}).get("enabled", True) and candidates:
        candidates = rank_candidates_visual(
            candidates,
            item_by_username,
            seeds,
            cfg["visual"],
            cfg.get("reference_matching", {}),
            negative_usernames=negative_refs,
        )
    else:
        for c in candidates:
            c.visual_similarity = None
            c.visual_rank = None

    print("[6/12] Creator Target Gate + combined ranking")
    gate_cfg = cfg.get("creator_target_gate", {})
    for c in candidates:
        meta = evaluate_creator_target(c, gate_cfg)
        c.creator_target_fit = meta["creator_target_fit"]
        c.creator_target_gate = meta["creator_target_gate"]
        c.creator_target_reason = meta["creator_target_reason"]
    print(f"  creator target scored (no reject): {len(candidates)}")

    if candidates:
        candidates = rank_candidates_combined(candidates, cfg.get("similarity_ranking", {}))

    # Optional quality threshold. Do not force-fill the requested result count
    # with weak candidates.
    qcfg = cfg.get("similarity_ranking", {})
    min_similarity = qcfg.get("min_combined_similarity")
    if min_similarity is not None and str(min_similarity).strip() != "":
        min_similarity = float(min_similarity)
        for c in candidates:
            c.quality_pass = bool(c.combined_similarity is not None and c.combined_similarity >= min_similarity)
        print(f"  quality threshold >= {min_similarity}: flag only, no reject")
    else:
        for c in candidates:
            c.quality_pass = True

    print("[7/12] Select accounts for Reel performance")
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
        print("[8/12] Reel tab scraping")
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
        print("[8/12] Reel tab scraping skipped")

    print("[9/12] Commercial filter + final scoring")
    commercial_cfg = cfg.get("commercial_filter", {})
    final_candidates = []
    for c in candidates:
        analyzed = c.username.lower() in {x.lower() for x in perf_usernames}
        metrics = reel_metrics.get(c.username.lower(), {})
        if analyzed:
            reason = commercial_reject_reason(metrics, commercial_cfg)
            c.commercial_flag = reason or ""
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
    final_candidates = analyzed + not_analyzed + unavailable_candidates

    print("[10/12] SQLite")
    store = SQLiteStore(cfg["output"]["sqlite_path"])
    store.save_candidates(final_candidates)
    store.save_posts(profile_posts + reels)
    store.close()

    print("[11/12] Excel")
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
        cfg["output"]["excel_path"],
    )

    print("\nDONE")
    print(f"Candidates exported: {len(final_candidates)}")
    print("Rejected: disabled in MVP v0.9 (signals are columns)")
    print(f"Reels scraped: {len(reels)}")
    print(f"Excel: {cfg['output']['excel_path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/campaign.yaml")
    args = parser.parse_args()
    main(args.config)
