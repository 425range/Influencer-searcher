from src.youtube.apify_client import YouTubeApify
from src.youtube.parser import discover_channels_from_search


def discover_candidate_channels(
    scraper: YouTubeApify,
    queries: list[str],
    per_query: int,
    max_channels: int,
    max_shorts: int = 0,
    max_streams: int = 0,
):
    # One Actor run can accept multiple search queries.
    items = scraper.search(
        queries=queries,
        max_results=per_query,
        max_shorts=max_shorts,
        max_streams=max_streams,
    )

    channels = discover_channels_from_search(items)

    # Preserve first appearance order.
    return channels[:max_channels]
