from collections import defaultdict
from statistics import mean, median


def _nums(xs):
    return [x for x in xs if isinstance(x, (int, float))]


def _mean(xs):
    xs = _nums(xs)
    return mean(xs) if xs else 0.0


def _median(xs):
    xs = _nums(xs)
    return median(xs) if xs else 0.0


def _ratio(a, b):
    return a / b if b else 0.0


def build_reel_metrics(reels, ad_target=5):
    grouped = defaultdict(list)
    for reel in reels:
        grouped[reel.username.lower()].append(reel)

    result = {}
    selected_ad_by_user = {}

    for username, xs in grouped.items():
        xs = sorted(xs, key=lambda p: p.timestamp or "", reverse=True)
        ad_all = [p for p in xs if p.is_ad]
        organic_all = [p for p in xs if not p.is_ad]
        selected_ads = ad_all[:int(ad_target)]
        selected_ad_by_user[username] = selected_ads

        ad_views = [p.views for p in selected_ads if p.views is not None]
        org_views = [p.views for p in organic_all if p.views is not None]
        ad_likes = [p.likes for p in selected_ads if p.likes is not None]
        ad_comments = [p.comments for p in selected_ads if p.comments is not None]
        ad_shares = [p.shares for p in selected_ads if p.shares is not None]

        avg_ad_views = _mean(ad_views)
        avg_org_views = _mean(org_views)
        total_ad_views = sum(ad_views)

        result[username] = {
            "reels_scanned": len(xs),
            "requested_ad_reels": int(ad_target),
            "found_ad_reels": len(ad_all),
            "ad_reels_sampled": len(selected_ads),
            "organic_reels_found": len(organic_all),
            "oldest_reel_date": xs[-1].timestamp if xs else "",
            "newest_reel_date": xs[0].timestamp if xs else "",
            "avg_ad_reel_views": round(avg_ad_views, 2),
            "median_ad_reel_views": round(_median(ad_views), 2),
            "avg_organic_reel_views": round(avg_org_views, 2),
            "median_organic_reel_views": round(_median(org_views), 2),
            "ad_view_ratio": round(_ratio(avg_ad_views, avg_org_views), 4),
            "avg_ad_likes": round(_mean(ad_likes), 2),
            "median_ad_likes": round(_median(ad_likes), 2),
            "avg_ad_comments": round(_mean(ad_comments), 2),
            "median_ad_comments": round(_median(ad_comments), 2),
            "avg_ad_shares": round(_mean(ad_shares), 2),
            "median_ad_shares": round(_median(ad_shares), 2),
            "ad_like_rate": round(_ratio(sum(ad_likes), total_ad_views), 4),
            "ad_comment_rate": round(_ratio(sum(ad_comments), total_ad_views), 4),
            "ad_share_rate": round(_ratio(sum(ad_shares), total_ad_views), 4),
            "ad_engagement_rate": round(
                _ratio(sum(ad_likes) + sum(ad_comments) + sum(ad_shares), total_ad_views), 4
            ),
            "ad_ratio_in_scanned_reels": round(_ratio(len(ad_all), len(xs)), 4),
        }

    return result, selected_ad_by_user


def commercial_reject_reason(metrics: dict, cfg: dict) -> str:
    if not metrics:
        return "no_reel_data" if cfg.get("reject_no_reel_data", False) else ""

    found = metrics.get("found_ad_reels", 0)
    ratio = metrics.get("ad_ratio_in_scanned_reels", 0)

    min_ads = cfg.get("min_ad_reels")
    max_ads = cfg.get("max_ad_reels_in_scan")
    max_ratio = cfg.get("max_ad_ratio")

    if min_ads is not None and found < min_ads:
        return f"ad_reels<{min_ads}"
    if max_ads is not None and found > max_ads:
        return f"ad_reels>{max_ads}"
    if max_ratio is not None and ratio > max_ratio:
        return f"ad_ratio>{max_ratio}"
    return ""
