# 2026 정부 AI 예산 PDF 데이터 재추출 구현계획서

## Context

기존 프로젝트에서 41개 부처 PDF로부터 533개 사업의 예산 데이터를 추출했으나, 기존 코드(`extract_all.py`)는 사용 불가하여 **처음부터 새로 작성**함.
기존 추출 과정에서 발견된 주요 문제(`report/비표준_데이터_처리과정.md` 참조):

1. **부처별 총괄표 헤더 변형** — "예산 총괄표", "지출계획 총괄표", "예산안 총괄표" 등
2. **열 구조 차이** — 표준 7열(추경 포함) vs 6열(추경 없음) 혼재
3. **PyMuPDF 텍스트 순서 문제** — 시각적 순서와 추출 순서 불일치
4. **신규사업 특수 표기** — "-", "순증", "신규" 등 다양한 마커

이 워크스페이스에서 새 추출 스크립트를 작성하고, 자동 검증 + 부처별 차이 리포트를 생성함.

---

## Phase 1: 환경 설정 및 파일 검증

### 1.1 Python 의존성

```
pdfplumber>=0.10.0    # 표 추출 (1차 방법, 셀 경계 보존)
PyMuPDF>=1.23.0       # 텍스트 추출 (2차 fallback)
pandas>=2.0.0         # 데이터 처리/출력
```

### 1.2 입력 파일 검증

- `resource/budget_depts/` 내 41개 PDF 존재 확인
- `resource/budget_depts/meta/00_사업목록_인덱스.json` 로드 — 533건 프로젝트별 페이지 범위 매핑
- JSON 구조: `부처별_사업목록[부처명].사업목록[].{사업명, 원본_시작페이지, 원본_끝페이지}`

---

## Phase 2: 추출 스크립트 — `verify_extract.py` 신규 작성

### 2.1 전체 구조

```
verify_extract.py
├── main()                          # 전체 오케스트레이션
├── load_index()                    # JSON 인덱스 로드
├── extract_project()               # 단일 프로젝트 추출 (fallback 체인)
│   ├── extract_via_pdfplumber()    # 1단계: 표 추출
│   ├── extract_via_pymupdf()       # 2~3단계: 텍스트 파싱
│   └── cross_validate()            # 4단계: 교차 검증
├── detect_column_structure()       # 헤더로 열 의미 자동 감지
├── parse_budget_table()            # 표 데이터 → 예산값 매핑
├── parse_number()                  # 숫자 문자열 파싱
├── extract_description()           # 사업설명 텍스트 추출
├── validate_record()               # 산술/일관성 검증
└── generate_report()               # 검증 리포트 생성
```

### 2.2 3단계 Fallback 추출

```
[1단계] pdfplumber 표 추출
  - extract_tables()로 페이지 내 표를 직접 추출
  - "사업명"/"목명" + "2026" 포함된 표 식별
  - 셀 경계가 보존되므로 열 밀림 없음
    ↓ 실패 시
[2단계] PyMuPDF 텍스트 파싱 1차
  - "가. (예산|지출계획|예산안) 총괄표" 패턴으로 시작점 탐지
  - "나. 사업설명자료"를 종료점으로 60줄 범위 탐색
  - 숫자 정규식으로 데이터 행 추출
    ↓ 숫자 6개 미만 시
[3단계] PyMuPDF 텍스트 파싱 2차
  - 종료점 제한 해제, 80줄 확장 탐색
  - 한글 15자 이상 문장 필터로 비데이터 행 제거
```

### 2.3 의미 기반 열 매핑 (핵심 개선사항)

**문제**: 부처마다 열 수와 헤더 명칭이 다름

```
7열: 사업명 | 2024결산 | 본예산 | 추경(A) | 요구안 | 본예산(B) | 증감(B-A) | (B-A)/A
6열: 사업명 | 2024결산 | 본예산(A) | 요구 | 조정(B) | 증감(B-A) | (B-A)/A
```

**해결**: 헤더 텍스트 분석으로 각 열의 의미를 자동 판별

```python
def detect_column_structure(header_cells):
    mapping = {}
    for i, cell in enumerate(header_cells):
        text = str(cell).strip()
        if "결산" in text or "2024" in text:
            mapping['budget_2024'] = i
        elif "추경" in text:
            mapping['budget_2025_sup'] = i
        elif "본예산" in text and ("2025" in context or "(A)" in text):
            mapping['budget_2025'] = i
        elif "요구" in text:
            mapping['budget_2026_req'] = i
        elif ("조정" in text or "본예산" in text) and ("(B)" in text):
            mapping['budget_2026'] = i
        elif "B-A" in text and ("/" in text or "%" in text):
            mapping['change_rate'] = i
        elif "B-A" in text or "증감" in text:
            mapping['change_amount'] = i
    return mapping
```

### 2.4 2025년 실제 예산 결정 로직

| 상황 | 실제 2025 예산 |
|------|--------------|
| 본예산 + 추경 모두 존재 | **추경** (4번째 열) |
| 본예산만 존재 | **본예산** (3번째 열) |
| 6열 구조 (추경 열 없음) | **본예산(A)** |

### 2.5 신규사업 판별 및 증감액 처리

- `budget_2024 is None AND budget_2025 is None` → `is_new = True`
- 증감률 열에 "순증" / "신규" → `is_new = True`
- 신규사업의 `change_amount` = `budget_2026` 값 그대로 기록 (기존 누락 수정)

### 2.6 숫자 파싱 규칙

- `△`, `▽` 접두어 → 음수 전환
- `-`, `–`, `―` 단독 → `None` (예산 없음)
- `순증`, `순감`, `신규` → 마커로 처리 (None 반환, is_new 플래그에 반영)
- 쉼표 제거, 연도(2020~2029) 숫자 무시
- 정규식: `r"[△▽]?[\d,]+\.?\d*|순증|순감|신규"`

### 2.7 총괄표 헤더 인식 패턴

```python
r"(가\.\s*)?(□\s*)?(예산|지출계획|예산안|지출계획안)\s*총괄표"
```

| 패턴 | 사용 부처 예시 |
|------|-------------|
| 가. 예산 총괄표 | 감사원, 경찰청 등 대부분 |
| 가. 지출계획 총괄표 | 과학기술정보통신부(R&D), 기후에너지환경부 |
| 가. 예산안 총괄표 | 기상청 등 |
| □ 예산 총괄표 | 방위사업청 |

### 2.8 사업설명 추출

- "사업목적" + ("내용" or "·" or "-") 패턴으로 시작점 탐지
- 다음 섹션 마커(번호 목록, "가.", "□사업근거") 전까지 수집

---

## Phase 3: 자동 검증 체계

### 3.1 레코드별 검증 (533건 전수)

| 검증 ID | 항목 | 로직 | 심각도 |
|--------|------|------|-------|
| V1 | 예산값 존재 | `budget_2026 is not None` | ERROR |
| V2 | 산술 일치 | `budget_2026 - actual_2025 ≈ change_amount` (±1) | WARN |
| V3 | 비율 일치 | `(change / actual_2025) × 100 ≈ change_rate` (±0.5%) | WARN |
| V4 | 신규 일관성 | 신규 → 2024/2025 = None | WARN |
| V5 | 비율 범위 | `change_rate` ∈ [-100%, 10000%] | WARN |
| V6 | 음수 예산 | 모든 예산값 ≥ 0 | ERROR |

### 3.2 교차 방법 검증

- pdfplumber와 PyMuPDF 결과를 모두 보유한 경우 비교
- 불일치 시 플래그 기록, pdfplumber 결과 우선

### 3.3 부처별 변이 카탈로그 생성

- 각 부처의 총괄표 헤더 형식
- 열 구조 (6열 / 7열)
- 신규사업 표기 방식 (-, 순증, 신규)
- 숫자 형식 (△/▽ 사용 여부, 소수점)

---

## Phase 4: 출력물

### 4.1 데이터 파일

| 파일 | 내용 |
|------|------|
| `data/budget_data_verified.csv` | 재추출 결과 (14열, 기존 스키마 호환) |
| `data/extraction_audit.csv` | 추출 방법, 검증 결과, 플래그 포함 |

### 4.2 CSV 스키마

```
dept_name, project_no, project_name, page_start, page_end,
budget_2024, budget_2025, budget_2025_sup,
budget_2026_req, budget_2026,
change_amount, change_rate,
is_new, description
```

- 단위: 백만원
- audit CSV 추가 열: `extraction_method`, `column_count`, `validation_flags`

### 4.3 검증 리포트 (`report/extraction_validation_report.md`)

- 전체 추출 통계 (추출 성공률, 산술 일치율, 교차검증 일치율)
- 부처별 요약 (사업수, 추출 방법, 검증 통과율)
- 검증 실패/경고 항목 목록
- 부처별 데이터 형식 변이 카탈로그

---

## Phase 5: 구현 순서

| 단계 | 작업 | 파일 |
|------|------|------|
| **1** | 환경 설정 (의존성 설치) | 터미널 |
| **2** | `verify_extract.py` 핵심 작성 — pdfplumber 1차 + 의미 기반 열 매핑 | `verify_extract.py` |
| **3** | PyMuPDF fallback 추가 | `verify_extract.py` |
| **4** | 사업설명 추출 + 신규사업 판별 추가 | `verify_extract.py` |
| **5** | 자동 검증 로직 및 리포트 생성 추가 | `verify_extract.py` |
| **6** | 파일럿 실행 (감사원·교육부·경찰청 등 3~5개 부처) 및 검증 | 실행/검토 |
| **7** | 전체 41개 부처 추출 실행 | 실행 |
| **8** | 검증 리포트 생성 및 플래그 항목 확인/수정 | `report/` |

---

## 참조 파일

| 파일 | 용도 |
|------|------|
| `resource/budget_depts/meta/00_사업목록_인덱스.json` | 533건 사업-페이지 매핑 (추출 드라이버) |
| `report/비표준_데이터_처리과정.md` | v1~v7 엣지케이스 이력 (파싱 규칙 참조) |
| `resource/budget_depts/*.pdf` (41개) | 원본 PDF |

---

## 검증 방법

구현 완료 후 다음으로 검증:

1. **파일럿 실행**: 감사원(1건), 교육부(11건), 과학기술정보통신부(192건), 경찰청(11건, 6열 변이)으로 추출 테스트
2. **산술 검증 통과율** 확인 (목표: 95% 이상)
3. 전체 533건 추출 후 `budget_2026` 합계가 약 2,735만 백만원 (= 27.4조원)인지 확인
4. 부처별 변이 카탈로그로 데이터 형식 차이 문서화

---

Q의 지침의 따라 Claude Code - claude-opus-4-6이 2026-03-09에 생성했습니다.
