from collections import defaultdict
from src.youtube.models import YouTubeChannel, YouTubeVideo


def to_int(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value

    text = str(value).replace(",", "").strip()
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def parse_video(item: dict) -> YouTubeVideo | None:
    channel_url = item.get("channelUrl")
    channel_name = item.get("channelName")
    video_url = item.get("url")

    if not channel_url or not channel_name or not video_url:
        return None

    return YouTubeVideo(
        channel_name=str(channel_name),
        channel_url=str(channel_url),
        video_id=str(item.get("id") or ""),
        title=str(item.get("title") or ""),
        url=str(video_url),
        description=str(item.get("text") or ""),
        date=str(item.get("date") or ""),
        views=to_int(item.get("viewCount")),
        likes=to_int(item.get("likes")),
        comments=to_int(item.get("commentsCount")),
        subscribers=to_int(item.get("numberOfSubscribers")),
    )


def discover_channels_from_search(items: list[dict]) -> list[YouTubeChannel]:
    result = {}

    for item in items:
        channel_url = item.get("channelUrl")
        channel_name = item.get("channelName")
        if not channel_url or not channel_name:
            continue

        key = str(channel_url).rstrip("/").lower()
        from_url = str(item.get("fromYTUrl") or "")

        if key not in result:
            result[key] = YouTubeChannel(
                channel_name=str(channel_name),
                channel_url=str(channel_url),
                subscribers=to_int(item.get("numberOfSubscribers")),
                description=str(item.get("channelDescription") or ""),
                source_queries=[from_url] if from_url else [],
            )
        elif from_url and from_url not in result[key].source_queries:
            result[key].source_queries.append(from_url)

    return list(result.values())


def enrich_channels_from_videos(
    candidates: list[YouTubeChannel],
    video_items: list[dict],
):
    by_url = {c.channel_url.rstrip("/").lower(): c for c in candidates}
    videos = []

    for item in video_items:
        video = parse_video(item)
        if not video:
            continue

        videos.append(video)

        key = video.channel_url.rstrip("/").lower()
        channel = by_url.get(key)
        if not channel:
            continue

        if video.subscribers is not None:
            channel.subscribers = video.subscribers

        channel_desc = item.get("channelDescription")
        if channel_desc:
            channel.description = str(channel_desc)

    return candidates, videos
