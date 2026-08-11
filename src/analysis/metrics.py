from statistics import mean, median
from collections import defaultdict


def _mean(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return mean(values) if values else 0.0


def _median(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return median(values) if values else 0.0


def build_metrics(posts):
    grouped = defaultdict(list)
    for p in posts:
        grouped[p.username.lower()].append(p)

    result = {}

    for username, xs in grouped.items():
        ad = [p for p in xs if p.is_ad]
        org = [p for p in xs if not p.is_ad]

        views = [p.views for p in xs if p.views is not None]
        ad_views = [p.views for p in ad if p.views is not None]
        org_views = [p.views for p in org if p.views is not None]

        likes = [p.likes or 0 for p in xs]
        comments = [p.comments or 0 for p in xs]

        avg_ad = _mean(ad_views)
        avg_org = _mean(org_views)

        result[username] = {
            "posts_analyzed": len(xs),
            "ad_posts": len(ad),
            "avg_views": round(_mean(views), 2),
            "median_views": round(_median(views), 2),
            "avg_ad_views": round(avg_ad, 2),
            "median_ad_views": round(_median(ad_views), 2),
            "avg_organic_views": round(avg_org, 2),
            "ad_to_organic_ratio": round(
                avg_ad / avg_org if avg_org else 0.0, 4
            ),
            "engagement_on_views": round(
                (sum(likes) + sum(comments)) / sum(views)
                if sum(views) else 0.0,
                4
            ),
        }

    return result
