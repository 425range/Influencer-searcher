# Influencer Discovery v0.9.2 — Simple GUI + Adaptive Search

## 사용자에게 보이는 설정

- 캠페인 이름
- 제품 / 캠페인
- 레퍼런스 계정
- 검색 해시태그
- 목표 후보 수
- 최소 / 최대 팔로워

가중치, 모델명, 검색 depth, Actor ID, 배치 크기, Target Gate 임계값 등은 GUI에서 숨겼습니다. 기존 YAML에는 유지되어 이후 개발/학습 단계에서 조정할 수 있습니다.

## 기본 검색 전략

레퍼런스와 해시태그를 모두 입력하면 Related Discovery는 전체 목표 후보 수의 30%를 상한으로 먼저 수집합니다. 이 비율은 GUI에 노출하지 않습니다.

그 후 Hashtag Discovery는 팔로워 범위에 들어오는 후보가 전체 목표 수에 도달할 때까지 검색 범위를 자동 확대합니다. 기본 검색 깊이는 50 → 100 → 200 → 400 → 500 results 입니다. 목표를 일찍 달성하면 즉시 중단합니다.

예: 목표 100명, 팔로워 30,000~500,000

```
Related: 최대 약 30명
Hashtag round 1: 50 rows
→ Profile follower 확인
→ 목표 미달 시 100 rows
→ 계속 부족하면 200 / 400 / 500 rows
→ follower-fit 후보 100명 달성 시 종료
```

레퍼런스만 입력하면 Related가 전체 목표까지 탐색하고, 해시태그만 입력하면 Hashtag가 전체 목표를 담당합니다.

## 후보 삭제 정책

팔로워 범위 밖, Creator Target 점수가 낮음, 카테고리 신호가 약함 등의 이유로 후보를 삭제하지 않습니다. Excel에 신호와 점수를 남깁니다. 레퍼런스 자체와 Negative Reference만 후보 목록에서 제외합니다.

## Billing estimate

로그에는 현재 기본 Actor 단가를 이용한 Discovery 추정 비용을 표시합니다.

- Hashtag: dami_studio/instagram-hashtag-scraper — $0.0004 / delivered post
- Profile: dami_studio/instagram-profile-scraper — $0.0007 / delivered profile

Related Actor 비용은 별도이므로 추정치에 포함하지 않습니다. 또한 Hashtag Actor에는 offset 입력이 없어 검색 범위를 확대하는 재실행에서 이전 게시물이 일부 다시 반환될 수 있습니다. 로그의 비용 추정은 각 실행에서 실제로 전달된 row를 누적해서 계산합니다.

## 실행

```bat
run_gui.bat
```

또는

```bash
python gui.py
```
