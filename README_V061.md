# v0.6.1 - Creator Gender Target Filter

GUI의 `타겟 / 제외` 탭에 `크리에이터 성별 필터`가 추가되었습니다.

- 전체
- 여성 중심
- 남성 중심

이 필터는 얼굴, 사진, 이름으로 성별을 추정하지 않습니다. 후보의 Bio 및 최근 Caption에 나타나는 명시적인 자기소개 표현만 사용합니다.

기본값 `여성 중심`에서는 남성 자기소개 신호가 충분히 강한 경우에만 후보를 제외합니다. 신호가 없거나 애매하면 후보를 유지합니다.

Excel Candidates 시트에 다음 컬럼이 추가됩니다.

- `gender_signal`
- `gender_target_match`
- `gender_evidence`

성별 필터에서 제외된 후보는 Rejected 시트에 `stage=gender_filter`로 남습니다.
