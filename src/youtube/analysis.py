import re
from collections import defaultdict
from statistics import mean, median


TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")


def mark_ads(videos, ad_keywords):
    keywords = [x.lower() for x in ad_keywords]

    for v in videos:
        text = f"{v.title} {v.description}".lower()
        v.is_ad = any(k in text for k in keywords)

    return videos


def build_channel_text(channel, videos):
    parts = [channel.channel_name, channel.description]
    for v in videos:
        parts.append(v.title)
        parts.append(v.description)
    return " ".join(x or "" for x in parts)


def category_scores(text: str, keyword_map: dict):
    text = (text or "").lower()
    scores = {}

    for category, keywords in keyword_map.items():
        if not keywords:
            scores[category] = 0.0
            continue

        hits = sum(1 for kw in keywords if kw.lower() in text)
        scores[category] = round(hits / len(keywords), 4)

    return scores


def token_set(text: str):
    stopwords = {
        "그리고", "하지만", "정말", "영상", "오늘", "대한",
        "입니다", "있는", "하는", "에서", "으로", "the", "and",
        "this", "that", "with", "youtube"
    }
    return {
        t.lower()
        for t in TOKEN_RE.findall(text or "")
        if t.lower() not in stopwords
    }


def seed_similarity(candidate_text: str, seed_texts: list[str]):
    c = token_set(candidate_text)
    if not c or not seed_texts:
        return 0.0

    best = 0.0
    for seed_text in seed_texts:
        s = token_set(seed_text)
        if not s:
            continue
        # Overlap coefficient works better than Jaccard when one channel
        # has much more text than the other.
        denominator = min(len(c), len(s))
        if denominator:
            best = max(best, len(c & s) / denominator)

    return round(min(best, 1.0), 4)


def _mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return mean(xs) if xs else 0.0


def _median(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return median(xs) if xs else 0.0


def metrics_by_channel(videos):
    grouped = defaultdict(list)
    for v in videos:
        grouped[v.channel_url.rstrip("/").lower()].append(v)

    result = {}

    for channel_key, xs in grouped.items():
        ads = [x for x in xs if x.is_ad]
        organic = [x for x in xs if not x.is_ad]

        all_views = [x.views for x in xs if x.views is not None]
        ad_views = [x.views for x in ads if x.views is not None]
        organic_views = [x.views for x in organic if x.views is not None]

        avg_ad = _mean(ad_views)
        avg_org = _mean(organic_views)

        engagement_values = []
        for x in xs:
            if x.views and x.views > 0:
                engagement_values.append(
                    ((x.likes or 0) + (x.comments or 0)) / x.views
                )

        result[channel_key] = {
            "videos_analyzed": len(xs),
            "ad_videos": len(ads),
            "avg_views": round(_mean(all_views), 2),
            "median_views": round(_median(all_views), 2),
            "avg_ad_views": round(avg_ad, 2),
            "median_ad_views": round(_median(ad_views), 2),
            "avg_organic_views": round(avg_org, 2),
            "ad_to_organic_ratio": round(
                avg_ad / avg_org if avg_org else 0.0, 4
            ),
            "avg_engagement_on_views": round(
                _mean(engagement_values), 4
            ),
        }

    return result
