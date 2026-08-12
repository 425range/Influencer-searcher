# Instagram SigLIP2 Visual Similarity PoC

## 기존 프로젝트에 추가할 파일
- `src/visual/`
- `prepare_visual_input.py`
- `visual_test.py`
- `config/visual.yaml`
- `requirements_visual.txt`

기존 `main.py`는 수정하지 않습니다.

## 실행 순서

1. 기존 Discovery
```bash
python main.py --config config/campaign.yaml
```

2. 패키지 설치
```bash
pip install -r requirements_visual.txt
```

3. Apify로 후보/Seed 최근 이미지 URL 추가
```bash
python prepare_visual_input.py --config config/visual.yaml
```

생성:
`output/candidates_with_images.xlsx`

4. SigLIP2 Visual Similarity
```bash
python visual_test.py --config config/visual.yaml
```

생성:
`output/visual_results.xlsx`

## 결과
핵심 컬럼:
- visual_rank
- username
- followers
- visual_similarity
- images_used_for_embedding

`visual_similarity`는 확률이 아니라 상대적 임베딩 유사도입니다.

## 첫 검증
후보 20~30명, 계정당 이미지 6장으로 시작하세요.
Top 10을 사람이 직접 보고 O/△/X를 매긴 뒤 Precision@10을 확인하면 됩니다.

## Cache
`cache/account_embeddings.pt`를 재사용합니다.
모델이나 이미지 수를 바꾸어 새 실험을 할 때는 이 파일을 삭제하세요.
