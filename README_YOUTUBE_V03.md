# YouTube Module v0.3

기존 Instagram v0.2 프로젝트에 YouTube 분석 모듈을 추가한 버전입니다.

## 목표

의사 채널 Seed를 기준으로:

1. Seed 채널 최근 영상 수집
2. YouTube 검색어로 후보 채널 탐색
3. 후보별 최근 영상 수집
4. 구독자 10만 이상 필터
5. 의사/의료 관련성 필터
6. 광고 영상 탐지
7. 광고/일반 영상 성과 비교
8. Seed 콘텐츠 유사도 계산
9. Ranking
10. SQLite + Excel 출력

## 실행

`.env`

```text
APIFY_TOKEN=your_token
```

설치:

```bash
pip install -r requirements.txt
```

실행:

```bash
python youtube_main.py --config config/doctor_youtube.yaml
```

## 출력

```text
output/doctor_youtube_candidates.xlsx
data/doctor_youtube.db
```

Excel에는 2개 시트가 생성됩니다.

### Channels
채널 단위 Ranking

- subscribers
- doctor_score
- seed_similarity
- avg_views
- avg_ad_views
- avg_organic_views
- ad_to_organic_ratio
- engagement
- final score
- human review columns

### Videos
수집한 영상 단위 raw data

- title
- URL
- views
- likes
- comments
- is_ad
- description

## v0.3 Seed의 의미

Instagram v0.2와 달리 YouTube에는 현재 이 PoC가 직접 사용할
`relatedProfiles` 같은 신호가 없습니다.

따라서 Seed 채널은:

- 최근 영상 title
- video description
- channel description

을 수집해 텍스트 기준점으로 사용합니다.

후보 채널도 같은 텍스트를 구성한 뒤 token overlap으로
`seed_similarity`를 계산합니다.

즉 Seed는 후보를 결과에 그냥 추가하는 것이 아니라
Ranking 기준으로 사용됩니다.

## 다음 버전 추천

v0.4에서는 token overlap을 embedding similarity로 교체하는 것이 좋습니다.

예:

Seed videos
→ embedding centroid

Candidate videos
→ embedding centroid

cosine similarity
→ seed_similarity

이렇게 하면 닥터프렌즈와 '같은 단어를 쓰는 채널'보다
'콘텐츠 의미/무드가 비슷한 채널'을 더 잘 잡을 수 있습니다.

## Apify Actor

기본값:

```text
streamers/youtube-scraper
```

입력 Adapter는:

```text
src/youtube/apify_client.py
```

한 곳에 격리되어 있습니다.

Actor input schema가 향후 바뀌더라도 이 파일만 수정하면
나머지 Discovery / Analysis / Storage 코드는 그대로 유지됩니다.
