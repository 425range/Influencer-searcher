# Influencer Discovery PoC v0.4

v0.3 Discovery + SigLIP visual ranking + Reel performance collector를 하나의 파이프라인으로 통합한 버전입니다.

## Pipeline

```text
Seed accounts
  ↓
Instagram Profile Scraper
  ↓
relatedProfiles + keyword candidates
  ↓
Follower / hard exclude filter
  ↓
SigLIP2 visual ranking
  ↓
Visual Top N only
  ↓
Instagram Reel Scraper
  ↓
Recent reels up to max_reels_to_scan
  ↓
Ad detection
  ↓
Most recent N ad reels
  ↓
mean / median views, likes, comments, shares
  ↓
commercial filter + final ranking
  ↓
Excel: Candidates / Reels / Rejected
```

## Important cost behavior

`ad_reels_target: 5` does **not** mean that only 5 reels are scraped.
The Actor must first scan enough recent reels to find ads.

Cost is bounded with:

```yaml
performance:
  ad_reels_target: 5
  max_reels_to_scan: 30
  only_posts_newer_than: "12 months"
```

The scraper obtains at most 30 recent reels per analyzed account (and only within the date range), then the code selects the 5 most recent ad reels from those results.

## Target / exclude keywords

```yaml
targeting:
  include_keywords:
    - 자기관리
    - 운동

  hard_exclude_keywords:
    - 육아
    - 키즈

  soft_exclude_keywords:
    - 뷰티

  hard_exclude_categories:
    - parenting
  hard_exclude_category_threshold: 0.20
```

Hard exclude → removed before SigLIP/Reel costs.
Soft exclude → retained, but receives a ranking penalty.

## Commercial constraints

```yaml
commercial_filter:
  min_ad_reels: null
  max_ad_reels_in_scan: null
  max_ad_ratio: null
```

Examples:

```yaml
# 광고 경험 최소 2개, 최근 스캔 범위에서 광고 비율 50% 초과 제외
commercial_filter:
  min_ad_reels: 2
  max_ad_ratio: 0.50
```

Rejected accounts remain in the `Rejected` sheet with a reason.

## Reel metrics

`Candidates` sheet includes:

- requested_ad_reels
- found_ad_reels
- ad_reels_sampled
- reels_scanned
- newest_reel_date / oldest_reel_date
- avg_ad_reel_views / median_ad_reel_views
- avg_ad_likes / median_ad_likes
- avg_ad_comments / median_ad_comments
- avg_ad_shares / median_ad_shares
- ad_like_rate / ad_comment_rate / ad_share_rate
- ad_engagement_rate
- ad_ratio_in_scanned_reels

`Reels` sheet keeps each scraped reel's:

- username
- upload_date
- reel_url
- is_ad
- selected_for_ad_metric
- ad_detection_reason
- paid_partnership
- views_or_plays
- likes
- comments
- shares
- caption

## Shares

Apify's Reel Scraper exposes `sharesCount` only when `includeSharesCount` is enabled, and the Actor currently labels that feature as available for paying users.

Default:

```yaml
performance:
  include_shares_count: false
```

If your Apify plan supports it:

```yaml
performance:
  include_shares_count: true
```

## Run

```bash
pip install -r requirements.txt
python main.py --config config/campaign.yaml
```

First SigLIP run downloads `google/siglip2-base-patch16-224` from Hugging Face.

Output:

```text
output/candidates_v04.xlsx
```
