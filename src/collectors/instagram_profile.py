from typing import Iterable
from apify_client import ApifyClient

PROFILE_ACTOR_ID = "apify/instagram-profile-scraper"


def _dataset_id(run):
    dataset_id = getattr(run, "default_dataset_id", None)
    if not dataset_id and isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        raise RuntimeError("Could not get Apify dataset id.")
    return dataset_id


def scrape_profiles(client: ApifyClient, usernames: Iterable[str]) -> list[dict]:
    usernames = list(dict.fromkeys(
        u.strip().lstrip("@")
        for u in usernames
        if u and u.strip()
    ))
    if not usernames:
        return []

    run = client.actor(PROFILE_ACTOR_ID).call(
        run_input={"usernames": usernames}
    )
    if run is None:
        raise RuntimeError("Instagram Profile Scraper failed.")

    dataset_id = _dataset_id(run)
    return list(client.dataset(dataset_id).iterate_items())


def parse_related_profiles(profile_item: dict) -> list[str]:
    related = profile_item.get("relatedProfiles") or []
    out = []

    for item in related:
        if not isinstance(item, dict):
            continue

        username = item.get("username")
        if username:
            out.append(username.strip().lstrip("@"))

    return out
