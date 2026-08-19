from apify_client import ApifyClient

from src.collectors.instagram_profile import scrape_profiles, parse_related_profiles
from src.models import Candidate


def discover_from_seeds(
    client: ApifyClient,
    seed_usernames: list[str],
    depth: int = 1,
    max_related_per_profile: int = 20,
    max_candidates: int = 100,
):
    """
    v0.7:
    Keep track of which original Reference accounts can reach each candidate.

    Example:
      candidate X is related to reference A and B
      -> reference_hits = [A, B]
      -> reference_overlap_count = 2

    This lets graph data act as a confidence signal instead of treating every
    relatedProfiles result as equally good.
    """
    seeds = [s.strip().lstrip("@") for s in seed_usernames if str(s).strip()]
    seed_set = {s.lower() for s in seeds}

    discovered: dict[str, Candidate] = {}
    visited = set()

    frontier = list(seeds)
    # lineage[frontier_username] = original references that led here.
    lineage = {s.lower(): {s} for s in seeds}

    for current_depth in range(depth):
        if not frontier or len(discovered) >= max_candidates:
            break

        items = scrape_profiles(client, frontier)
        next_frontier = []

        item_by_username = {
            str(item.get("username", "")).lower(): item
            for item in items
            if item.get("username")
        }

        for parent_username in frontier:
            parent_key = parent_username.lower()
            if parent_key in visited:
                continue
            visited.add(parent_key)

            profile_item = item_by_username.get(parent_key)
            if not profile_item:
                continue

            parent_origins = set(lineage.get(parent_key, []))
            related = parse_related_profiles(profile_item)[:max_related_per_profile]

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

    total_refs = max(len(seeds), 1)
    for c in discovered.values():
        c.reference_overlap_count = len(c.reference_hits)
        c.reference_overlap_ratio = c.reference_overlap_count / total_refs

        # Direct matches are more trustworthy than depth-2 matches.
        depth_factor = 1.0 if c.discovery_depth <= 1 else 0.70
        c.graph_similarity = min(1.0, c.reference_overlap_ratio * depth_factor)

    return list(discovered.values())
