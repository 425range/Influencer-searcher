# Influencer Discovery PoC

UI 없이 실행하는 인플루언서 탐색 PoC입니다.

## 현재 범위

1. Campaign YAML 입력
2. Apify Google Search Scraper로 Instagram 후보 탐색
3. Seed influencer 강제 포함
4. 선택한 Instagram Apify Actor를 통한 프로필/게시물 수집
5. 광고성 게시물 룰 기반 탐지
6. 카테고리 적합도 계산
7. 평균/중앙 조회수, 광고 조회수, Engagement 계산
8. 후보 Score 계산
9. SQLite 저장
10. Excel 출력 + 사람 검토용 컬럼 생성

---

## 디렉토리

```text
influencer_discovery_poc/
├─ config/
│  └─ campaign.yaml
├─ data/
├─ output/
├─ src/
│  ├─ discovery/
│  │  └─ apify_google.py
│  ├─ collectors/
│  │  └─ apify_instagram.py
│  ├─ analysis/
│  │  ├─ ad_detector.py
│  │  ├─ category.py
│  │  ├─ metrics.py
│  │  └─ scoring.py
│  ├─ storage/
│  │  └─ sqlite_store.py
│  ├─ exporters/
│  │  └─ excel_exporter.py
│  ├─ config_loader.py
│  └─ models.py
├─ .env.example
├─ requirements.txt
├─ README.md
└─ main.py
```

## 설치

Python 3.10+ 권장.

Windows / Anaconda:

```bash
conda create -n influencer_poc python=3.11 -y
conda activate influencer_poc

pip install -r requirements.txt
```

`.env.example`을 `.env`로 복사:

```text
APIFY_TOKEN=...
INSTAGRAM_ACTOR_ID=...
```

## 1차 실행: Discovery only

Instagram Actor ID를 비워두어도 됩니다.

```bash
python main.py --config config/campaign.yaml
```

이 경우 Google 검색을 통해 후보 Instagram URL을 수집하고,
`output/candidates.xlsx`를 만듭니다.

## Instagram 데이터까지 수집

Apify Store에서 사용할 Instagram scraper Actor를 선택한 뒤:

```text
INSTAGRAM_ACTOR_ID=creator/actor-name
```

을 `.env`에 입력합니다.

Actor마다 입력/출력 스키마가 다를 수 있으므로
`src/collectors/apify_instagram.py`의 아래 세 함수만 맞춰주면 됩니다.

```python
build_input()
parse_profile()
parse_post()
```

그 외의 DB, 분석, Score, Excel 출력 코드는 그대로 유지합니다.

## 출력

### SQLite
`data/influencers.db`

Tables:
- influencers
- posts
- reviews

### Excel
`output/candidates.xlsx`

사람이 다음 컬럼을 직접 채우도록 설계했습니다.

- review_status
- reject_reason
- reviewer_note

이 Human Review 데이터를 다음 버전에서 Ranking 모델 개선 데이터로 사용할 수 있습니다.

## 다음 구현 권장 순서

### v0.2
- 실제 사용할 Instagram Actor 확정 및 adapter 연결
- 광고 탐지 정밀화
- 브랜드명 추출
- Reel / Feed 분리
- 최근 N개월 조건

### v0.3
- LLM 카테고리 분류
- Seed influencer similarity
- reject reason 학습/반영
- campaign/search run 테이블 추가

### v0.4
- FastAPI wrapper
- PostgreSQL 전환
- CRM / Email 모듈 연결
