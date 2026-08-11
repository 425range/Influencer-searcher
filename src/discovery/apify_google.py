import re
from apify_client import ApifyClient
from src.models import Candidate

PROFILE_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?(?:\?.*)?$"
)

EXCLUDED = {
    "p", "reel", "reels", "stories", "explore",
    "accounts", "direct", "about", "developer"
}


def normalize_profile(url):
    if not url:
        return None

    m = PROFILE_RE.match(url.strip())
    if not m:
        return None

    username = m.group(1)
    if username.lower() in EXCLUDED:
        return None

    return username


def discover_by_keywords(
    client: ApifyClient,
    queries: list[str],
    actor_id: str,
    max_pages_per_query: int,
    result_limit: int,
):
    if not queries:
        return []

    run_input = {
        "queries": "\\n".join(
            f'site:instagram.com "{q}" -inurl:/p/ -inurl:/reel/'
            for q in queries
        ),
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
        return []

    dataset_id = getattr(run, "default_dataset_id", None)
    if not dataset_id and isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")

    if not dataset_id:
        return []

    result = {}

    for item in client.dataset(dataset_id).iterate_items():
        search_term = (
            (item.get("searchQuery") or {}).get("term")
            or item.get("query")
            or ""
        )

        organic = (
            item.get("organicResults")
            or item.get("nonPromotedSearchResults")
            or item.get("searchResults")
            or []
        )

        for entry in organic:
            username = normalize_profile(entry.get("url") or entry.get("link"))
            if not username:
                continue

            key = username.lower()
            result.setdefault(
                key,
                Candidate(
                    username=username,
                    profile_url=f"https://www.instagram.com/{username}/",
                    source="keyword",
                    source_seed="",
                    discovery_depth=0,
                )
            )

            if len(result) >= result_limit:
                return list(result.values())

    return list(result.values())
