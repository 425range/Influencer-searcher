# Influencer Discovery PoC v0.9 MVP

핵심 변경:

- Google 검색은 기본 비활성화.
- Related Accounts + Hashtag Search 두 가지 Discovery를 사용.
- Hashtag Actor 기본값: `publicsignallabs/instagram-hashtag-scraper`.
- Profile Enrichment 기본값: `dami_studio/instagram-profile-scraper`.
- Hashtag 검색 결과의 caption에서 `#광고`, `#협찬`, `#제품제공`, `#유료광고` 동반 여부를 바로 기록.
- 동일 작성자가 여러 해시태그에서 발견되면 계정 단위로 합산.
- Rejected 시트 제거. 팔로워 범위, 타깃 제외 신호, Creator Target Gate, 상업성 필터는 삭제 대신 컬럼/플래그로 남김.

## Candidates 주요 신규 컬럼

- `discovery_sources`
- `source_hashtags`
- `hashtag_discovery_posts`
- `hashtag_ad_posts`
- `hashtag_ad_ratio`
- `hashtag_ad_tags`
- `hashtag_latest_timestamp`
- `follower_in_range`
- `targeting_flag`
- `category_flag`
- `commercial_flag`

## 권장 첫 테스트

- Reference: 3~5개
- Related target: 30~50
- Hashtag: 3~5개
- Hashtag당 결과: 50
- 일반 게시물 + Reel 모두 포함
- Reel performance는 Top 10만

해시태그 검색은 게시물 자체를 최종 후보로 쓰는 것이 아니라 작성자 username을 발견하는 용도입니다. 발견 후 저가 Profile Scraper로 follower/bio/latestPosts를 보강합니다.
