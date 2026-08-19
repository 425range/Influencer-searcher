# Influencer Discovery PoC v0.7

v0.7의 목적은 후보 수를 늘리는 것이 아니라 **마케터가 고른 여러 Reference 계정과 실제로 비슷한 후보를 더 안정적으로 위로 올리는 것**입니다.

## 주요 변경

### 1. Reference Set
레퍼런스 계정을 1~2개 Seed 평균으로 뭉개지 않습니다.

후보마다 각 Reference와 유사도를 계산하고, 가장 가까운 Reference Top K 평균을 사용합니다.

GUI:
- `가까운 Reference Top K = 2`

Reference가 다양할 때 "아무도 닮지 않은 평균 벡터"가 생기는 문제를 줄입니다.

### 2. Graph overlap
Instagram relatedProfiles는 후보 생성에만 사용하되 다음 값을 기록합니다.

- `reference_hits`
- `reference_overlap_count`
- `reference_overlap_ratio`
- `graph_similarity`

여러 Reference의 추천망에서 반복해서 발견된 후보가 더 높은 graph confidence를 가집니다.

### 3. Dynamic Weight
Caption이 없는 계정에 Caption 점수 0을 주지 않습니다.

기본 가중치:
- Visual 0.55
- Caption 0.25
- Hashtag 0.10
- Graph 0.10

Caption 데이터가 없으면 해당 0.25를 제거하고 나머지 신호를 자동 재정규화합니다.

### 4. Robust Visual
최근 서로 다른 게시물 대표 이미지 각각을 Reference 계정과 비교합니다.

추가 컬럼:
- `visual_reference_similarity`
- `visual_post_median_similarity`
- `nearest_visual_reference`

한두 장이 우연히 Reference와 비슷한 경우 계정 전체 Visual 점수를 과도하게 끌어올리는 것을 줄이기 위해 median 신호를 섞습니다.

### 5. Quality Threshold
GUI의 `최소 통합 유사도`를 설정하면 기준보다 낮은 후보는 결과 수를 채우기 위해 억지로 포함하지 않습니다.

처음에는 빈칸으로 두고 실제 결과 분포를 본 뒤 threshold를 정하는 것을 권장합니다.

## 추천 첫 테스트

Reference 계정은 가능하면 마케터가 실제로 "좋다"고 고른 5~10명을 넣습니다.

비용 절약 설정:
- 추천 Depth: 1
- Related 최대: 10~15
- Seed 후보 최대: 50
- Reel 분석 Top N: 5
- 광고 Reel 목표: 3
- Reel 최대 탐색: 10

Visual / Caption / Hashtag / Graph 계산은 기존 Profile Scraper 결과와 로컬 모델을 재사용합니다.
추가 비용의 대부분은 Reel 상세 수집 단계에서 발생합니다.

## 결과에서 볼 컬럼

- reference_hits
- reference_overlap_count
- graph_similarity
- nearest_visual_reference
- visual_reference_similarity
- visual_post_median_similarity
- nearest_text_reference
- caption_similarity
- nearest_hashtag_reference
- hashtag_similarity
- ranking_signals_used
- combined_similarity

특히 Caption을 거의 쓰지 않는 계정의 `ranking_signals_used`에 caption이 빠지고 다른 신호만 사용되는지 확인하세요.
