from src.models import Post


def mark_ads(posts: list[Post], ad_keywords: list[str]) -> list[Post]:
    normalized_keywords = [k.lower() for k in ad_keywords]

    for post in posts:
        text = (post.caption or "").lower()
        post.is_ad = any(keyword in text for keyword in normalized_keywords)

    return posts
