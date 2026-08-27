from apify_client import ApifyClient

from src.collectors.instagram_profile import scrape_profiles, parse_related_profiles
from src.models import Candidate


DEFAULT_RELATED_FALLBACK_ACTOR = "instagram-scraper/instagram-related-profiles"


def _dataset_id(run):
    dataset_id = getattr(run, "default_dataset_id", None)
    if not dataset_id and isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")
    return dataset_id


def _fallback_related_discovery(
    client: ApifyClient,
    seeds: list[str],
    depth: int,
    max_candidates: int,
    actor_id: str,
):
    """
    Fallback only when the official Profile Scraper returns ZERO related
    profiles for the whole reference set.

    The fallback actor uses:
      instagramUsernames
      scrapeDepth: 0=direct related, 1=related-of-related
      maxResults

    It is NOT used on a normal run, so it does not add cost unless needed.
    """
    actor_depth = max(0, int(depth) - 1)
    max_results = max(10, int(max_candidates) + len(seeds))

    print(
        "  related fallback: official Profile Scraper returned 0 related "
        f"profiles; trying {actor_id}"
    )
    run = client.actor(actor_id).call(
        run_input={
            "instagramUsernames": seeds,
            "scrapeDepth": actor_depth,
            "skipLatestPosts": True,
            "scrapeFacebookProfile": False,
            "maxResults": max_results,
        }
    )
    if run is None:
        print("  related fallback: actor returned no run")
        return []

    dataset_id = _dataset_id(run)
    if not dataset_id:
        print("  related fallback: no dataset id")
        return []

    rows = list(client.dataset(dataset_id).iterate_items())
    print(f"  related fallback: dataset rows={len(rows)}")
    return rows


def discover_from_seeds(
    client: ApifyClient,
    seed_usernames: list[str],
    depth: int = 1,
    max_related_per_profile: int = 20,
    max_candidates: int = 100,
    profile_cache: dict | None = None,
    use_related_fallback: bool = True,
    related_fallback_actor_id: str = DEFAULT_RELATED_FALLBACK_ACTOR,
):
    """
    v0.8.1:
    - caches Profile Scraper results for later enrichment
    - logs relatedProfiles counts per Reference
    - robust parser support is handled by parse_related_profiles()
    - if ALL references return 0 relatedProfiles, optionally tries a dedicated
      related-profile Actor as a fallback
    """
    seeds = [s.strip().lstrip("@") for s in seed_usernames if str(s).strip()]
    seed_set = {s.lower() for s in seeds}
    profile_cache = profile_cache if profile_cache is not None else {}

    discovered: dict[str, Candidate] = {}
    visited = set()
    frontier = list(seeds)
    lineage = {s.lower(): {s} for s in seeds}

    total_primary_related = 0

    for current_depth in range(depth):
        if not frontier or len(discovered) >= max_candidates:
            break

        # Reuse profiles already fetched during this run; scrape only missing.
        missing = [u for u in frontier if u.lower() not in profile_cache]
        if missing:
            items = scrape_profiles(client, missing)
            for item in items:
                username = str(item.get("username", "")).strip()
                if username:
                    profile_cache[username.lower()] = item

        item_by_username = {
            u.lower(): profile_cache.get(u.lower())
            for u in frontier
            if profile_cache.get(u.lower()) is not None
        }

        next_frontier = []

        for parent_username in frontier:
            parent_key = parent_username.lower()
            if parent_key in visited:
                continue
            visited.add(parent_key)

            profile_item = item_by_username.get(parent_key)
            if not profile_item:
                print(f"    related {parent_username}: profile missing")
                continue

            related_all = parse_related_profiles(profile_item)
            related = related_all[:max_related_per_profile]
            total_primary_related += len(related_all)

            if current_depth == 0:
                keys = sorted(profile_item.keys())
                print(
                    f"    related {parent_username}: parsed={len(related_all)} "
                    f"(using up to {len(related)}), "
                    f"relatedProfiles_present={'relatedProfiles' in profile_item}"
                )
                if not related_all:
                    # Useful for diagnosing future Actor schema changes without
                    # dumping private profile data or large nested payloads.
                    related_like_keys = [
                        k for k in keys
                        if any(t in k.lower() for t in ("related", "suggest", "similar"))
                    ]
                    print(f"      related-like keys: {related_like_keys}")

            parent_origins = set(lineage.get(parent_key, []))

            for username in related:
                key = username.lower()
                if key in seed_set:
                    continue

                if key not in discovered:
                    discovered[key] = Candidate(
                        username=username,
                        profile_url=f"https://www.instagram.com/{username}/",
                        source="seed_related",
                        source_seed=parent_username,
                        discovery_depth=current_depth + 1,
                        reference_hits=sorted(parent_origins),
                    )
                else:
                    c = discovered[key]
                    c.reference_hits = sorted(set(c.reference_hits) | parent_origins)
                    if c.discovery_depth <= 0 or (current_depth + 1) < c.discovery_depth:
                        c.discovery_depth = current_depth + 1
                        c.source_seed = parent_username

                lineage.setdefault(key, set()).update(parent_origins)
                if key not in visited:
                    next_frontier.append(username)

                if len(discovered) >= max_candidates:
                    break

            if len(discovered) >= max_candidates:
                break

        frontier = list(dict.fromkeys(next_frontier))

    # Dedicated fallback when the official Profile Scraper yielded no related
    # candidates at all. This addresses intermittent/Actor-side cases where
    # profile info succeeds but relatedProfiles is empty.
    if (
        not discovered
        and seeds
        and use_related_fallback
        and total_primary_related == 0
    ):
        try:
            rows = _fallback_related_discovery(
                client=client,
                seeds=seeds,
                depth=depth,
                max_candidates=max_candidates,
                actor_id=related_fallback_actor_id,
            )

            for row in rows:
                username = str(row.get("username", "")).strip().lstrip("@")
                if not username or username.lower() in seed_set:
                    continue

                row_depth = int(row.get("depth") or 0)
                # Root rows are depth=0. Direct related rows are depth=1.
                if row_depth <= 0:
                    continue

                source_username = (
                    row.get("source_username")
                    or row.get("sourceUsername")
                    or ""
                )
                source_username = str(source_username).strip().lstrip("@")

                # Only keep requested discovery depth.
                if row_depth > max(1, depth):
                    continue

                origins = []
                if source_username.lower() in seed_set:
                    origins = [source_username]
                else:
                    # For depth>1, exact original lineage may not be present in
                    # a flat row. Keep the parent as provenance; graph score
                    # remains conservative.
                    origins = [source_username] if source_username else []

                key = username.lower()
                if key not in discovered:
                    discovered[key] = Candidate(
                        username=username,
                        profile_url=f"https://www.instagram.com/{username}/",
                        source="seed_related_fallback",
                        source_seed=source_username,
                        discovery_depth=row_depth,
                        reference_hits=sorted(set(origins)),
                    )
                else:
                    c = discovered[key]
                    c.reference_hits = sorted(set(c.reference_hits) | set(origins))

                if len(discovered) >= max_candidates:
                    break

            print(f"  related fallback candidates: {len(discovered)}")
        except Exception as exc:
            # Google search can still provide candidates; don't crash the whole
            # pipeline solely because the optional fallback actor failed.
            print(f"  related fallback failed: {type(exc).__name__}: {exc}")

    total_refs = max(len(seeds), 1)
    for c in discovered.values():
        c.reference_overlap_count = len(c.reference_hits)
        c.reference_overlap_ratio = c.reference_overlap_count / total_refs

        depth_factor = 1.0 if c.discovery_depth <= 1 else 0.70
        c.graph_similarity = min(1.0, c.reference_overlap_ratio * depth_factor)

    print(
        f"  related discovery: primary_related_seen={total_primary_related}, "
        f"unique_candidates={len(discovered)}"
    )
    return list(discovered.values())
