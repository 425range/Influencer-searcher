# Influencer Discovery PoC v0.9.1

## 목적
v0.9의 Hashtag Discovery를 독립적으로 검증할 수 있도록 설정을 분리하고, Hashtag Actor를 `dami_studio/instagram-hashtag-scraper`로 변경했습니다.

## 변경사항

### 1) Related Search ON/OFF
캠페인 탭에 `관련 추천 계정 검색 사용` 체크박스를 추가했습니다.

- OFF + Hashtag ON: Hashtag-only 테스트
- ON + Hashtag OFF: Related-only 테스트
- ON + Hashtag ON: 두 Discovery 결과를 합쳐 사용

### 2) Hashtag Actor 변경
기본 Actor:
`dami_studio/instagram-hashtag-scraper`

입력은 `hashtags`와 `resultsLimit`만 전달합니다. 이 Actor는 이미지/영상/캐러셀 결과를 함께 반환하므로 Posts/Reels 체크박스는 제거했습니다.

### 3) 광고 신호
Actor가 제공하는 `hashtags[]`와 caption에서 추출한 해시태그를 합쳐 `광고`, `협찬`, `제품제공`, `유료광고` 등을 검사합니다.

### 4) 진단 로그 강화
Hashtag 실행 시 아래가 출력됩니다.

```
hashtag actor: dami_studio/instagram-hashtag-scraper
hashtag discovery: hashtags=1, results_limit=20
hashtag discovery result: dataset_rows=..., usable_media_rows=..., rows_with_owner=..., ad_media_rows=..., unique_creators=...
```

### 5) 첫 테스트 권장

```
Related Search: OFF
Hashtag Search: ON
Hashtag: 올영세일
해시태그당 결과 수: 20
```

정상이면 `Candidates`의 `source`가 `hashtag`로 나오고 `source_hashtags`, `hashtag_discovery_posts`, `hashtag_ad_posts`, `hashtag_ad_tags`가 채워집니다.
