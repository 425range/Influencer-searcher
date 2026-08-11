import re
from typing import List
from apify_client import ApifyClient

from src.models import Candidate


INSTAGRAM_PROFILE_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?(?:\?.*)?$"
)

EXCLUDED_PATHS = {
    "p", "reel", "reels", "stories", "explore", "accounts",
    "direct", "about", "developer"
}


def normalize_instagram_profile(url: str):
    if not url:
        return None

    url = url.strip()
    match = INSTAGRAM_PROFILE_RE.match(url)
    if not match:
        return None

    username = match.group(1)
    if username.lower() in EXCLUDED_PATHS:
        return None

    return username, f"https://www.instagram.com/{username}/"


def _extract_organic_results(item: dict):
    # Apify Google Search actor output has changed names over time.
    # Support the common variants instead of coupling to one exact schema.
    for key in (
        "organicResults",
        "nonPromotedSearchResults",
        "searchResults",
    ):
        value = item.get(key)
        if isinstance(value, list):
            return value
    return []


def discover_instagram_candidates(
    client: ApifyClient,
    queries: List[str],
    actor_id: str,
    max_pages_per_query: int = 1,
    result_limit: int = 100,
) -> List[Candidate]:
    search_queries = [
        f'site:instagram.com "{query}" -inurl:/p/ -inurl:/reel/'
        for query in queries
    ]

    run_input = {
        "queries": "\n".join(search_queries),
        "maxPagesPerQuery": max_pages_per_query,
        "geminiSearch": {"enableGemini": False},
        "perplexitySearch": {
            "enablePerplexity": False,
            "returnImages": False,
            "returnRelatedQuestions": False,
        },
        "chatGptSearch": {"enableChatGpt": False},
        "copilotSearch": {"enableCopilot": False},
        "maximumLeadsEnrichmentRecords": 0,
    }

    run = client.actor(actor_id).call(run_input=run_input)
    if run is None:
        raise RuntimeError("Google Search Actor run failed.")

    dataset_id = getattr(run, "default_dataset_id", None)
    if not dataset_id and isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")

    if not dataset_id:
        raise RuntimeError("Could not find default dataset id from Actor run.")

    candidates = {}
    for item in client.dataset(dataset_id).iterate_items():
        search_term = item.get("searchQuery", {}).get("term") or item.get("query") or ""
        for result in _extract_organic_results(item):
            url = result.get("url") or result.get("link")
            parsed = normalize_instagram_profile(url)
            if not parsed:
                continue

            username, profile_url = parsed
            key = username.lower()
            if key not in candidates:
                candidates[key] = Candidate(
                    username=username,
                    profile_url=profile_url,
                    source_query=search_term,
                )

            if len(candidates) >= result_limit:
                return list(candidates.values())

    return list(candidates.values())
