# 전체 부처 예산 데이터 추출 파이프라인 구현 계획서

전체 41개 부처, 533개 사업의 PDF에서 예산액과 사업 내용을 추출하여 대시보드용 DB를 구성합니다.

## 목차

1. [데이터 추출 스크립트](#1-데이터-추출-스크립트)
2. [데이터 저장 구조](#2-데이터-저장-구조)
3. [검증 계획](#3-검증-계획)

---

## 1. 데이터 추출 스크립트

### `extract_all.py`

- `00_사업목록_인덱스.json`을 순회하며 모든 부처·사업 PDF를 파싱
- **예산 총괄표 추출**: PyMuPDF 텍스트에서 "가. 예산 총괄표" ~ "나. 사업설명자료" 구간의 숫자를 정규식으로 파싱
  - 추출 항목: `2024 결산`, `2025 본예산`, `2025 추경`, `2026 요구안`, `2026 본예산`, `증감액`, `증감률`
  - 숫자 형식: 쉼표가 포함된 정수(예: `12,508`), 마이너스 표시(`△`), 순증/순감 등 처리
  - 헤더 행(연도/컬럼명) 필터링: "사업명", "결산", "예산", "본예산", "추경", "요구", "증감", "단위" 등 키워드 포함 행을 건너뜀
  - 4자리 연도 숫자(2020~2029) 자동 제외
  - 사업명에 포함된 숫자(예: "112시스템운영")를 예산 데이터에서 분리하기 위한 사업명 텍스트 매칭 로직
- **사업목적·내용 추출**: "사업목적" 키워드 기반으로 텍스트 블록 수집 (유니코드 변이 `·`, `･`, `.` 모두 대응)
- 예외 처리: 해당 섹션이 없는 사업에 대해 빈값(`None`) 저장 및 로그 출력

## 2. 데이터 저장 구조

### `data/budget_data.csv`

추출 결과를 CSV로 저장 (pandas DataFrame)

| Column | Description |
|---|---|
| dept_name | 부처명 |
| project_no | 사업 번호 |
| project_name | 사업명 |
| budget_2024 | 2024년 결산 (백만원) |
| budget_2025 | 2025년 본예산 (백만원) |
| budget_2025_sup | 2025년 추경 (백만원) |
| budget_2026_req | 2026년 요구안 (백만원) |
| budget_2026 | 2026년 본예산 (백만원) |
| change_amount | 증감액 (백만원) |
| change_rate | 증감률 (%) |
| is_new | 신규사업 여부 (2026만 편성) |
| description | 사업목적·내용 요약 |

### `data/budget.db` (SQLite)

- `projects` 테이블: CSV와 동일한 스키마
- `dept_summary` 뷰: 부처별 사업수·예산 총액
- `new_projects` 뷰: 신규사업 목록
- `budget_changes` 뷰: 증감 분석 (증가/감소/동결 구분)

## 3. 검증 계획

### 자동 검증

- 추출 스크립트 실행 후 CSV 파일이 생성되는지 확인
- 전체 533개 사업 중 파싱 성공률을 로그로 출력

```bash
source .venv/bin/activate && python extract_all.py
```

- SQLite DB에서 대시보드용 쿼리가 정상 동작하는지 확인

```bash
source .venv/bin/activate && python -c "
import sqlite3, pandas as pd
conn = sqlite3.connect('data/budget.db')
print(pd.read_sql('SELECT * FROM projects LIMIT 5', conn))
print(pd.read_sql('SELECT * FROM dept_summary', conn))
conn.close()
"
```

---

> 본 문서는 2026년 3월 7일에 작성되었으며, Google Antigravity가 Q의 지침에 따라 생성함.
