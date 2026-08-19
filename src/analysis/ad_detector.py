from src.models import Post


def detect_ad(post: Post, keywords: list[str]) -> tuple[bool, str]:
    if post.paid_partnership:
        return True, "paid_partnership"

    text = (post.caption or "").lower()
    for keyword in keywords:
        if keyword.lower() in text:
            return True, f"keyword:{keyword}"

    return False, ""


def mark_ads(posts: list[Post], keywords: list[str]):
    for post in posts:
        post.is_ad, post.ad_detection_reason = detect_ad(post, keywords)
    return posts
