# Influencer Searcher v0.8.2 update
Base: `query-develop` v0.8.1.

Changes: remove active SigLIP/Visual pipeline and visual result columns; add non-visual ranking (Topic 55%, Hashtag 20%, Reference graph 15%, Caption 10%); add recent hashtag discovery; pre-filter hashtag authors by follower count before Profile Scraper; add per-hashtag yield logs; add GUI hashtag controls; default 100 posts/tag and expansion OFF.

Before running, restore any old v0.7 patch changes:

```bash
git checkout query-develop
git restore main.py gui.py config/campaign.yaml src/analysis/scoring.py
```

Copy this package into repo root and run:

```bash
python upgrade_query_develop_to_v082.py
python gui.py
```

First test: 1-3 specific hashtags, 100 posts/tag, expansion OFF. Check `unique_authors`, `follower_qualified`, and `yield` in the log before increasing the search volume.
