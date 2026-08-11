from src.models import Post


def mark_ads(posts: list[Post], keywords: list[str]):
    keywords = [k.lower() for k in keywords]

    for post in posts:
        text = (post.caption or "").lower()
        post.is_ad = any(k in text for k in keywords)

    return posts
