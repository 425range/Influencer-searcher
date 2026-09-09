# Influencer Discovery PoC v0.8

v0.8은 v0.7 실제 결과에서 확인된 세 문제를 수정합니다.

1. 명시적 성별 표현이 없는 계정이 `unknown`으로 그대로 통과
2. raw Caption cosine이 0.97~0.98 근처에 몰려 변별력이 낮음
3. relatedProfiles graph overlap이 "타깃 적합"이 아니라 단순 인맥/네트워크를 반영할 수 있음

## 1) Creator Target Gate

성별을 얼굴에서 추정하지 않습니다.

대신 Ranking 전에 다음 신호로 계정 전체의 타깃 적합도를 확인합니다.

- Positive Reference Visual similarity
- 최근 게시물 Visual consistency (median)
- Topic Profile similarity
- Optional Negative Reference contrast
- Bio/Caption의 명시적 성별 mismatch는 기존 early filter 유지

기본 Visual gate:
- min_visual_reference = 0.89
- min_visual_median = 0.82
- 둘 다 미달이면 reject

이 값은 v0.7 실험 결과의 분포를 바탕으로 한 시작값이므로 다음 테스트 후 조정하세요.

## 2) Topic Profile

raw caption-to-caption cosine은 Excel에 진단값으로 남지만 기본 Ranking에서는 weight=0입니다.

Caption/Bio embedding을 다음 Topic 축에 투영한 "상대적 패턴"을 비교합니다.

- fitness
- selfcare
- fashion
- beauty
- office
- travel
- food
- parenting
- couple
- entertainment

E5 cosine의 공통 baseline을 줄이기 위해 Topic vector를 평균 중심화한 뒤 Reference와 비교합니다.

## 3) Dynamic Ranking

기본:
- Visual 0.60
- Topic Profile 0.25
- Hashtag 0.10
- Graph 0.05
- Raw Caption 0.00

데이터가 없는 신호는 0점 처리하지 않고 제거 후 나머지 weight를 재정규화합니다.

## 4) Negative Reference

GUI Content 유사도 탭에 `Negative Reference (선택)` 입력창이 추가되었습니다.

예:
- 이전 검색 결과에서 마케터가 "이 사람은 명확히 타깃 아님"이라고 판단한 계정

Negative Reference는 후보 생성에 사용되지 않고 Positive Reference와의 상대적 거리 비교에만 사용됩니다.

처음 실행에서는 비워도 됩니다.
v0.7에서 명확히 잘못 나온 계정을 2~5개 넣고 재실험하면 분별력이 더 좋아질 수 있습니다.

## 새 Excel 컬럼

- visual_negative_similarity
- visual_target_margin
- topic_similarity
- topic_negative_similarity
- topic_target_margin
- topic_profile
- creator_target_fit
- creator_target_gate
- creator_target_reason

Rejected 시트의 `stage=creator_target_gate`를 확인하면 어떤 후보가 어떤 이유로 탈락했는지 볼 수 있습니다.

## 추천 첫 설정

Positive Reference: 실제 마케터 선호 계정 5~10개
Negative Reference: 처음에는 빈칸 또는 이전 오답 2~5개

- Reference Top K: 2
- Visual: 0.60
- Topic: 0.25
- Hashtag: 0.10
- Graph: 0.05
- Raw Caption: 0.00
- 최소 Visual Reference: 0.89
- 최소 Visual 게시물 중앙값: 0.82
- Reel 분석 대상: 5~10
