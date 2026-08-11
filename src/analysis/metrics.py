from statistics import mean, median
from collections import defaultdict
from src.models import Post


def _safe_mean(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return mean(values) if values else 0.0


def _safe_median(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return median(values) if values else 0.0


def build_metrics(posts: list[Post]) -> dict[str, dict]:
    grouped = defaultdict(list)
    for post in posts:
        grouped[post.username.lower()].append(post)

    output = {}

    for username, user_posts in grouped.items():
        ad_posts = [p for p in user_posts if p.is_ad]
        organic_posts = [p for p in user_posts if not p.is_ad]

        views = [p.views for p in user_posts if p.views is not None]
        ad_views = [p.views for p in ad_posts if p.views is not None]
        organic_views = [p.views for p in organic_posts if p.views is not None]

        likes = [p.likes for p in user_posts if p.likes is not None]
        comments = [p.comments for p in user_posts if p.comments is not None]

        avg_views = _safe_mean(views)
        avg_ad_views = _safe_mean(ad_views)
        avg_org_views = _safe_mean(organic_views)

        ad_ratio = (
            avg_ad_views / avg_org_views
            if avg_org_views > 0
            else 0.0
        )

        total_views = sum(views)
        engagement_on_views = (
            (sum(likes) + sum(comments)) / total_views
            if total_views > 0
            else 0.0
        )

        output[username] = {
            "post_count_analyzed": len(user_posts),
            "ad_post_count": len(ad_posts),
            "avg_views": round(avg_views, 2),
            "median_views": round(_safe_median(views), 2),
            "avg_ad_views": round(avg_ad_views, 2),
            "median_ad_views": round(_safe_median(ad_views), 2),
            "avg_organic_views": round(avg_org_views, 2),
            "ad_to_organic_view_ratio": round(ad_ratio, 4),
            "engagement_on_views": round(engagement_on_views, 4),
        }

    return output
