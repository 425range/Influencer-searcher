# Influencer Discovery PoC v0.8.1 — Discovery Stability Patch

v0.8.1은 추천/랭킹 모델을 바꾸지 않고 Discovery 단계의 안정성을 수정한 버전입니다.

## 수정 1. Google multi-line query

v0.8은 여러 검색문을 `\\n`(문자 두 개)으로 연결해 Apify Google Search Scraper가 전체를 한 검색어로 처리할 수 있었습니다.

v0.8.1:
- GUI 한 줄 = Google 독립 Query 1개
- 실제 newline(`\n`)으로 Actor에 전달
- config에 여러 줄이 하나의 string으로 들어와도 다시 분리
- 실행 로그에 준비된 Query 수와 각 Query를 표시

정상 로그 예:
```
google discovery: 4 independent queries
google query 1: site:instagram.com "임신주차" ...
google query 2: site:instagram.com "예비맘" ...
```

## 수정 2. Related profile parsing

공식 Apify Instagram Profile Scraper의 현재 output schema는 `relatedProfiles`를 지원합니다.
v0.8.1 파서는 아래 형태를 방어적으로 지원합니다.

- `relatedProfiles`
- `related_profiles`
- suggested/similar profile variants
- nested `node / user / edges / items / nodes`

Reference별로 다음 진단 로그가 출력됩니다.
```
related hellochaeyeon: parsed=18 (using up to 15), relatedProfiles_present=True
```

## 수정 3. Related fallback

공식 Profile Scraper가 모든 Reference에서 profile 정보는 반환했지만 relatedProfiles가 전부 0인 경우에만
별도의 Related Profiles Actor를 fallback으로 호출합니다.

기본:
```yaml
discovery:
  use_related_fallback: true
  related_fallback_actor_id: instagram-scraper/instagram-related-profiles
```

정상적으로 relatedProfiles가 나오면 fallback은 실행되지 않으므로 추가 비용이 없습니다.
fallback이 실행되면 로그에 명확히 표시됩니다.

## 수정 4. Reference Profile 재사용

Discovery에서 이미 수집한 Reference Profile 결과를 메모리 캐시에 저장합니다.

기존:
```
Reference Profile Scrape
→ Discovery
→ Reference Profile Scrape 다시 실행
→ Enrichment
```

v0.8.1:
```
Reference Profile Scrape
→ Discovery
→ cache 재사용
→ Candidate만 추가 Profile Scrape
```

## 수정 5. Candidate=0 비용 방지

Discovery 결과가 0명이면 candidate enrichment를 위해 Reference를 다시 크롤링하지 않습니다.
파이프라인은 빈 결과 Excel을 만들 수 있도록 계속 진행하지만 추가 candidate profile 호출은 하지 않습니다.

## 실행 후 확인할 로그

특히 첫 단계의 아래 네 줄을 확인하세요.

```
related <reference>: parsed=N
related discovery: primary_related_seen=N, unique_candidates=N
google discovery: N independent queries
discovery summary: related=N, google=N, merged_unique=N
```

여기서 `primary_related_seen=0`이면 fallback 실행 여부를 확인하면 됩니다.
