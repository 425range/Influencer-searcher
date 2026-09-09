# Influencer Discovery PoC v0.6

v0.5.1 GUI에 **Caption + Hashtag Content Similarity**를 추가한 버전입니다.

## 핵심 변경

기존 Profile Scraper에서 이미 확보한 `latestPosts`를 재사용합니다.
따라서 Content Similarity 때문에 Instagram/Profile Apify 호출이 추가되지 않습니다.

```text
Reference Accounts
    ↓
Profile Scraper 1회
    ↓
relatedProfiles / keyword candidates
    ↓
Target / Exclude Filter
    ↓
┌───────────────────────┬────────────────────────┐
│ Caption + Hashtag     │ SigLIP Visual          │
│ Content Similarity    │ Similarity             │
└───────────┬───────────┴────────────┬───────────┘
            └───────────┬────────────┘
                        ↓
              Combined Similarity
                        ↓
                    Top N
                        ↓
                 Reel Scraper
                        ↓
              Advertising Performance
```

## Caption Similarity

기본 모델:

```text
intfloat/multilingual-e5-small
```

`transformers`와 `torch`를 사용해 로컬에서 실행합니다.
OpenAI API나 LLM 토큰을 사용하지 않습니다.

기본 설정:

```yaml
text_similarity:
  enabled: true
  model_name: intfloat/multilingual-e5-small
  recent_posts: 8
  include_ads: false
  include_bio: true
  caption_weight: 0.8
  hashtag_weight: 0.2
  batch_size: 16
```

`include_ads: false`이면 광고로 판별된 Profile Feed 게시물은 계정의 평소 Content Style 비교에서 제외됩니다.

## Hashtag Similarity

Caption embedding과 분리해 Jaccard similarity로 계산합니다.
범용/광고 hashtag는 제외할 수 있습니다.

```yaml
stop_hashtags:
  - 광고
  - 협찬
  - 제품제공
  - 유료광고
  - 일상
  - 데일리
  - 좋아요
```

## Combined Ranking

기본값:

```yaml
similarity_ranking:
  visual_weight: 0.6
  content_weight: 0.4
```

Content 자체는 기본적으로:

```text
Caption Semantic Similarity 80%
Hashtag Similarity          20%
```

입니다.

한쪽 데이터가 없는 경우에는 존재하는 점수만으로 자동 재정규화합니다.

## Excel Candidates 추가 컬럼

```text
combined_rank
visual_rank
visual_similarity
caption_similarity
hashtag_similarity
shared_hashtags
content_similarity
text_posts_used
combined_similarity
```

`shared_hashtags`는 후보와 Reference가 실제로 공유한 hashtag를 확인하기 위한 검수 컬럼입니다.

## GUI

새 탭:

```text
Content 유사도
```

에서 다음을 수정할 수 있습니다.

- 분석 ON/OFF
- Text Model
- 최근 게시물 N개
- 광고 게시물 포함 여부
- Bio 포함 여부
- Caption / Hashtag 가중치
- Batch Size
- 무시할 Hashtag
- Visual / Content 통합 가중치

## Cache

```text
cache/text_embeddings.pt
```

에 계정별 Caption embedding을 저장합니다.
Caption 내용 또는 주요 Text 설정이 바뀌면 fingerprint가 바뀌어 해당 계정만 다시 계산됩니다.

## 실행

```bash
pip install -r requirements.txt
python gui.py
```

첫 Text 분석 실행에서는 Hugging Face 모델을 한 번 다운로드합니다.
그 후에는 로컬 cache를 사용합니다.

## 추천 첫 테스트

비교 품질 확인용으로:

```text
Content 최근 게시물: 6~8
광고 제외: ON
Caption Weight: 0.8
Hashtag Weight: 0.2
Visual Weight: 0.6
Content Weight: 0.4
Reel 분석 Top N: 10
```

정도로 시작하는 것을 권장합니다.
