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


def _clean_username(value):
    if not value:
        return None
    value = str(value).strip().lstrip("@")
    if value.startswith("http"):
        # Accept https://www.instagram.com/username/
        parts = value.split("/")
        try:
            idx = parts.index("instagram.com")
            value = parts[idx + 1]
        except (ValueError, IndexError):
            return None
    value = value.split("?")[0].strip("/")
    if not value:
        return None
    return value


def _collect_related_usernames(value, out):
    """
    Accept several shapes seen across Instagram/Apify actors:
      relatedProfiles: [{username: ...}]
      related_profiles: [{username: ...}]
      edges: [{node: {username: ...}}]
      strings / URLs
    Only called on values already known to represent a 'related' field.
    """
    if value is None:
        return

    if isinstance(value, str):
        username = _clean_username(value)
        if username:
            out.append(username)
        return

    if isinstance(value, list):
        for item in value:
            _collect_related_usernames(item, out)
        return

    if not isinstance(value, dict):
        return

    username = (
        value.get("username")
        or value.get("userName")
        or value.get("handle")
    )
    if username:
        cleaned = _clean_username(username)
        if cleaned:
            out.append(cleaned)

    # Common nested graph/list wrappers.
    for key in ("node", "user", "profile", "edges", "items", "nodes", "results"):
        if key in value:
            _collect_related_usernames(value.get(key), out)


def parse_related_profiles(profile_item: dict) -> list[str]:
    if not isinstance(profile_item, dict):
        return []

    related_values = []
    # Official Apify Profile Scraper currently documents relatedProfiles.
    # Alternate actors and older/current pass-through shapes may use snake_case
    # or nested related/suggested keys.
    for key in (
        "relatedProfiles",
        "related_profiles",
        "relatedprofiles",
        "suggestedProfiles",
        "suggested_profiles",
        "similarProfiles",
        "similar_profiles",
    ):
        if key in profile_item and profile_item.get(key) is not None:
            related_values.append(profile_item.get(key))

    # Defensive scan for top-level keys containing both a relation hint and
    # profile/user/account semantics, without recursively treating unrelated
    # fields (latestPosts, tagged users, etc.) as related profiles.
    for key, value in profile_item.items():
        lowered = str(key).lower()
        if key in {
            "relatedProfiles", "related_profiles", "relatedprofiles",
            "suggestedProfiles", "suggested_profiles",
            "similarProfiles", "similar_profiles",
        }:
            continue
        if (
            any(token in lowered for token in ("related", "suggested", "similar"))
            and any(token in lowered for token in ("profile", "user", "account", "edge"))
        ):
            related_values.append(value)

    out = []
    for value in related_values:
        _collect_related_usernames(value, out)

    # Preserve order, remove duplicates and self.
    self_username = str(profile_item.get("username", "")).lower()
    deduped = []
    seen = set()
    for username in out:
        key = username.lower()
        if not username or key == self_username or key in seen:
            continue
        seen.add(key)
        deduped.append(username)

    return deduped
