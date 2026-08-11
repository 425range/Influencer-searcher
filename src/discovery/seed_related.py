from collections import deque
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
    seeds = [s.strip().lstrip("@") for s in seed_usernames]
    seed_set = {s.lower() for s in seeds}

    discovered: dict[str, Candidate] = {}
    visited = set()
    frontier = seeds

    for current_depth in range(depth):
        if not frontier or len(discovered) >= max_candidates:
            break

        # Batch profile request. It gives profile metrics + Instagram relatedProfiles.
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
                    )

                if key not in visited:
                    next_frontier.append(username)

                if len(discovered) >= max_candidates:
                    break

            if len(discovered) >= max_candidates:
                break

        frontier = list(dict.fromkeys(next_frontier))

    return list(discovered.values())
