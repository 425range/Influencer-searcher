from apify_client import ApifyClient


class YouTubeApify:
    """
    Adapter for streamers/youtube-scraper.

    Actor input schema used here:
      - searchQueries
      - startUrls
      - maxResults
      - maxResultsShorts
      - maxResultStreams

    If the Actor changes later, only this adapter should need modification.
    """

    def __init__(self, client: ApifyClient, actor_id: str):
        self.client = client
        self.actor_id = actor_id

    @staticmethod
    def _dataset_id(run):
        dataset_id = getattr(run, "default_dataset_id", None)
        if not dataset_id and isinstance(run, dict):
            dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            raise RuntimeError("Could not obtain Apify default dataset id.")
        return dataset_id

    def _run(self, run_input: dict) -> list[dict]:
        run = self.client.actor(self.actor_id).call(run_input=run_input)
        if run is None:
            raise RuntimeError(f"YouTube Actor failed: {self.actor_id}")

        dataset_id = self._dataset_id(run)
        return [
            item
            for item in self.client.dataset(dataset_id).iterate_items()
            if not item.get("error")
        ]

    def search(self, queries: list[str], max_results: int,
               max_shorts: int = 0, max_streams: int = 0) -> list[dict]:
        if not queries:
            return []

        return self._run({
            "searchQueries": queries,
            "maxResults": max_results,
            "maxResultsShorts": max_shorts,
            "maxResultStreams": max_streams,
        })

    def scrape_channels(self, channel_urls: list[str], max_results: int,
                        max_shorts: int = 0, max_streams: int = 0) -> list[dict]:
        urls = [{"url": u} for u in dict.fromkeys(channel_urls) if u]
        if not urls:
            return []

        return self._run({
            "startUrls": urls,
            "maxResults": max_results,
            "maxResultsShorts": max_shorts,
            "maxResultStreams": max_streams,
        })
