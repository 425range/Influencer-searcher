# Influencer Discovery PoC v0.7

최신 변경사항은 `README_V07.md`를 확인하세요.

# v0.6 GUI + Content Similarity

이번 버전은 기존 SigLIP Visual Similarity에 Caption/Hashtag Content Similarity를 추가합니다. 자세한 내용은 `README_V06.md`를 참고하세요.

# Influencer Discovery PoC v0.2

이번 버전은 v0.1의 두 가지 핵심 문제를 수정합니다.

1. seed 계정이 단순히 결과에 추가되기만 하던 문제
2. followers 정보가 없는 계정이 최소 팔로워 필터를 통과하던 문제

## 핵심 변화

### Seed discovery
`lamuzes`, `2dumi`를 Instagram Profile Scraper에 넣고
각 프로필의 `relatedProfiles`를 후보로 가져옵니다.

depth=2인 경우:

seed
→ related profile
→ related profile의 related profile

까지 확장합니다.

### Hard follower filtering
모든 후보를 `apify/instagram-profile-scraper`로 다시 조회해서
`followersCount`를 가져온 뒤 필터합니다.

기본 설정:

```yaml
min_followers: 30000
max_followers: 500000
allow_unknown_followers: false
```

따라서 followers가 30,000 미만이거나 아예 조회되지 않은 계정은
최종 Excel에 들어가지 않습니다.

## 실행

```bash
conda activate influencer_poc
pip install -r requirements.txt
```

`.env`

```text
APIFY_TOKEN=...
```

실행:

```bash
python main.py --config config/campaign.yaml
```

## 테스트 권장

처음에는 Google keyword discovery를 끄고
Seed similarity pipeline만 확인하는 것이 좋습니다.

```yaml
use_keyword_search: false
seed_expansion_depth: 1
max_related_per_profile: 10
max_seed_candidates: 20
```

정상 동작이 확인되면:

```yaml
use_keyword_search: true
seed_expansion_depth: 2
max_related_per_profile: 20
max_seed_candidates: 120
```

으로 확대하세요.

## Excel에서 확인할 컬럼

- source
  - `seed_related`: seed 계정 기반 발견
  - `keyword`: 검색 쿼리 기반 발견

- source_seed
  - 어떤 계정을 통해 발견됐는지

- discovery_depth
  - seed에서 몇 단계 떨어져 있는지

- followers
  - 실제 follower filter에 사용

- seed_similarity
  - v0.2에서는 Instagram related profile 여부 중심의 단순 점수

## 다음 버전

v0.3에서는 seed 계정과 후보 계정의 bio + caption을 embedding하여
실제 콘텐츠 유사도를 계산하는 것이 좋습니다.

현재 v0.2는 "Instagram이 related profile로 연결했는가"를
가장 강한 similarity signal로 사용합니다.


## YouTube v0.3

See `README_YOUTUBE_V03.md` and run `youtube_main.py`.
