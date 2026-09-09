# Influencer Discovery PoC v0.5 GUI

v0.4의 Discovery / SigLIP / Reel Performance 파이프라인 위에 Tkinter GUI를 추가한 테스트 버전입니다.

## 실행

기존 conda 환경에서:

```bash
pip install -r requirements.txt
python gui.py
```

Windows에서는 `run_gui.bat`을 더블클릭해도 됩니다.

## 현재 GUI에서 수정 가능한 항목

### 캠페인 / Discovery
- 캠페인명 / 제품명
- Reference Instagram username
- 검색어
- 키워드 검색 ON/OFF
- 최소/최대 팔로워
- Seed expansion depth
- Related 계정 수
- Candidate 최대 수

### Target / Exclusion
- Include keywords
- Hard exclude keywords
- Soft exclude keywords
- Soft exclude penalty
- Hard exclude categories
- Category reject threshold

### Visual
- SigLIP ON/OFF
- Model name
- Images per account
- Batch size
- Reel performance 분석 대상 Top N

### Reel / 광고 성과
- 최근 광고 Reel N개
- 최대 Reel 탐색 수
- 최대 lookback 기간
- Pinned Reel 제외
- Shares 수집 옵션
- 광고 최소/최대 개수
- 광고 비율 제한
- Reel 데이터 없는 계정 제외

## 동작 방식

GUI에서 값을 수정하고 `설정 저장`을 누르면 `config/campaign.yaml`에 저장됩니다.

`분석 시작`을 누르면 기존 `main.py` 파이프라인을 별도 thread에서 실행합니다. 실행 로그는 GUI 아래쪽에 표시됩니다.

결과는 기본적으로:

```text
output/candidates_v05.xlsx
```

에 저장됩니다.

## API Key

현재 테스트 버전은 기존과 동일하게 프로젝트 루트 `.env` 파일의:

```text
APIFY_TOKEN=...
```

을 사용합니다.

회사 API 계정 구조가 정해지면 GUI에 API Key 입력란을 추가하고, 저장 방식도 Windows Credential Manager 또는 별도 안전한 저장 방식으로 변경하는 것을 권장합니다.

## 다음 패키징 단계

기능 검증 후:

1. GUI와 pipeline 경로 정리
2. API key 입력/저장 UI
3. 실행 취소 및 상세 progress bar
4. Nuitka standalone build
5. Windows 다른 PC에서 smoke test
6. installer 제작

순서로 진행하면 됩니다.
