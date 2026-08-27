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

    m = PROFILE_RE.match(str(url).strip())
    if not m:
        return None

    username = m.group(1)
    if username.lower() in EXCLUDED:
        return None

    return username


def _normalize_queries(queries):
    """
    GUI/config values may arrive as:
      ["query A", "query B"]
    or accidentally as:
      ["query A\nquery B"]

    Flatten both forms into independent queries.
    """
    out = []
    for value in queries or []:
        if value is None:
            continue
        for line in str(value).replace("\\n", "\n").splitlines():
            q = line.strip()
            if q:
                out.append(q)
    return list(dict.fromkeys(out))


def discover_by_keywords(
    client: ApifyClient,
    queries: list[str],
    actor_id: str,
    max_pages_per_query: int,
    result_limit: int,
):
    queries = _normalize_queries(queries)
    if not queries:
        print("  google discovery: 0 query")
        return []

    prepared = [
        f'site:instagram.com "{q}" -inurl:/p/ -inurl:/reel/'
        for q in queries
    ]

    # IMPORTANT: Apify Google Search Scraper expects one query per *real*
    # newline. v0.8 used "\\n" (literal backslash+n), which made the Actor
    # treat the whole block as one query.
    run_input = {
        "queries": "\n".join(prepared),
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

    print(f"  google discovery: {len(prepared)} independent queries")
    for idx, q in enumerate(prepared, start=1):
        print(f"    google query {idx}: {q}")

    run = client.actor(actor_id).call(run_input=run_input)
    if run is None:
        print("  google discovery: actor returned no run")
        return []

    dataset_id = getattr(run, "default_dataset_id", None)
    if not dataset_id and isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")

    if not dataset_id:
        print("  google discovery: no dataset id")
        return []

    result = {}
    organic_count = 0

    for item in client.dataset(dataset_id).iterate_items():
        organic = (
            item.get("organicResults")
            or item.get("nonPromotedSearchResults")
            or item.get("searchResults")
            or []
        )

        organic_count += len(organic)

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
                print(
                    f"  google discovery: organic={organic_count}, "
                    f"profile_candidates={len(result)} (limit reached)"
                )
                return list(result.values())

    print(
        f"  google discovery: organic={organic_count}, "
        f"profile_candidates={len(result)}"
    )
    return list(result.values())
