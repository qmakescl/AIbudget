"""
AIbudget - 전체 부처 예산사업 데이터 추출 파이프라인
===================================================
00_사업목록_인덱스.json을 기반으로 41개 부처, 533개 사업 PDF에서
예산 총괄표 데이터와 사업목적·내용을 추출하여 CSV 및 SQLite DB로 저장합니다.
"""

import json
import os
import re
import sqlite3
import sys

import fitz  # PyMuPDF
import pdfplumber
import pandas as pd

# ── 경로 설정 ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCE_DIR = os.path.join(BASE_DIR, "resource", "budget_depts")
INDEX_PATH = os.path.join(RESOURCE_DIR, "meta", "00_사업목록_인덱스.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "budget_data.csv")
DB_PATH = os.path.join(DATA_DIR, "budget.db")

os.makedirs(DATA_DIR, exist_ok=True)


# ── 유틸리티 함수 ─────────────────────────────────────────

def parse_number(s: str | None) -> float | None:
    """
    예산 숫자 문자열을 float로 변환합니다.
    - 쉼표 제거, △ → 음수, 순증/순감 처리, '-' → None
    """
    if s is None:
        return None
    s = s.strip()
    if s in ("-", "–", "―", "", "순증"):
        return None
    if s == "순감":
        return None

    negative = False
    if s.startswith("△") or s.startswith("▽"):
        negative = True
        s = s[1:]

    s = s.replace(",", "").replace(" ", "")
    # 퍼센트 기호 제거
    s = s.replace("%", "")

    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


def extract_text_for_project(doc, local_start: int, local_end: int) -> str:
    """PDF 문서에서 특정 페이지 범위의 텍스트를 추출합니다."""
    text = ""
    for p_idx in range(local_start, min(local_end + 1, len(doc))):
        text += doc[p_idx].get_text() + "\n"
    return text


# ── 예산 총괄표 파싱 ──────────────────────────────────────

# 헤더/메타 행에 자주 등장하는 키워드 (이 키워드가 있는 행은 데이터 행이 아님)
_HEADER_KEYWORDS = [
    "사업명", "결산", "예산", "본예산", "추경", "요구", "증감", "단위",
    "백만원", "(B-A)", "(A)", "(B)", "/A", "년", "조정",
    "목명", "목별", "계획", "정부안", "확정", "이관",
    "사업구조", "구조개편", "기능별", "내역사업",
    "현액", "집행액", "불용액", "이월액", "당초", "수정",
]


def _is_header_line(line: str) -> bool:
    """헤더/메타 라인인지 판단합니다."""
    for kw in _HEADER_KEYWORDS:
        if kw in line:
            return True
    return False


def _is_year_number(s: str) -> bool:
    """4자리 연도 숫자(2020~2029)인지 판단합니다."""
    s_clean = s.replace(",", "").replace("△", "").replace("▽", "")
    try:
        v = int(float(s_clean))
        return 2020 <= v <= 2029
    except (ValueError, OverflowError):
        return False


def extract_budget_summary(text: str, project_name: str) -> dict:
    """
    텍스트에서 '가. 예산 총괄표' 영역을 찾아 예산 데이터를 추출합니다.
    헤더 행(연도/컬럼명)을 건너뛰고, 사업명 데이터 행의 숫자만 추출합니다.

    Returns:
        dict with keys: budget_2024, budget_2025, budget_2025_sup,
                        budget_2026_req, budget_2026, change_amount, change_rate
    """
    result = {
        "budget_2024": None,
        "budget_2025": None,
        "budget_2025_sup": None,
        "budget_2026_req": None,
        "budget_2026": None,
        "change_amount": None,
        "change_rate": None,
    }

    lines = text.split("\n")

    # "가. 예산 총괄표" / "가. 지출계획 총괄표" / "가. 예산안 총괄표" / "가. 지출계획안 총괄표" 위치 찾기
    budget_start = None
    for i, line in enumerate(lines):
        if re.search(r"(예산|지출계획|예산안|지출계획안)\s*총괄표", line):
            budget_start = i
            break

    if budget_start is None:
        return result

    # 예산 총괄표 ~ 다음 섹션 사이의 데이터 행만 수집
    # 헤더 키워드가 포함된 행과 빈 행은 건너뜀
    # 사업명 텍스트가 포함된 행도 사업명 행이므로 별도 처리
    
    # 사업명에서 숫자 토큰 추출 (이 숫자들은 예산 금액이 아님)
    _name_numbers = set(re.findall(r"\d+", project_name))
    # 사업명을 공백·괄호 제거하여 매칭 키 생성
    _name_key = re.sub(r"[\s\(\)（）]", "", project_name)

    def _collect_data_lines(start, end_offset, use_break):
        """총괄표 영역에서 데이터 행을 수집합니다.
        
        '목명' 또는 '사업명' 열 헤더를 서브 앵커로 찾아,
        그 이후의 데이터만 수집합니다. PyMuPDF 텍스트 추출 순서
        문제(□기능별 하위표 데이터 혼입)를 방지합니다.
        """
        # 서브 앵커 검색: '목명' 또는 '사업명' 단독 행
        data_start = start
        for i in range(start, min(start + end_offset, len(lines))):
            line = lines[i].strip()
            if use_break and "사업설명자료" in line:
                break
            if line in ("목명", "사업명"):
                data_start = i + 1
                break
        
        collected = []
        for i in range(data_start, min(start + end_offset, len(lines))):
            line = lines[i].strip()
            # break 조건: '사업설명자료'는 항상 중단
            if use_break and "사업설명자료" in line:
                break
            # □: 데이터를 이미 수집한 경우에만 중단
            if use_break and line.startswith("□") and collected:
                break
            # 헤더 행 건너뛰기
            if _is_header_line(line):
                continue
            # 빈 행 건너뛰기
            if not line:
                continue
            # 페이지 번호 건너뛰기 (예: "- 20 -")
            if re.match(r"^-\s*\d+\s*-$", line):
                continue
            # 꺾쇠·주석 메타 행 건너뛰기
            if line.startswith("<") or line.startswith("※") or line.startswith("* "):
                continue
            # ○ 접두어 행 건너뛰기 (○기능별 분류 등)
            if line.startswith("○") or line.startswith("․"):
                continue
            # 2차 시도에서만: 한글 문장 행(15자 이상) 건너뛰기
            if not use_break:
                korean_chars = len(re.findall(r"[가-힣]", line))
                if korean_chars >= 15:
                    continue
            # 사업명 텍스트가 포함된 행 건너뛰기
            line_key = re.sub(r"[\s\(\)（）]", "", line)
            if len(_name_key) >= 6 and _name_key[:6] in line_key:
                continue
            collected.append(line)
        return collected

    def _extract_numbers(d_lines):
        """데이터 행에서 예산 숫자를 추출합니다.
        '-' 단독은 해당 연도에 예산이 없음을 뜻합니다 (DASH 마커).
        """
        num_pattern = re.compile(r"[△▽]?[\d,]+\.?\d*|순증|순감|신규")
        nums = []
        for line in d_lines:
            # '-' 단독 (예산 없음 표시)
            if line == "-":
                nums.append("DASH")
                continue
            found = num_pattern.findall(line)
            for token in found:
                if _is_year_number(token):
                    continue
                token_clean = token.replace(",", "").replace("△", "").replace("▽", "")
                if token_clean in _name_numbers:
                    continue
                nums.append(token)
        return nums

    def _parse_token(token):
        """숫자 토큰을 파싱합니다. DASH는 None으로 변환."""
        if token == "DASH":
            return None
        return parse_number(token)

    # 1차 시도: '사업설명자료' break 사용 (정확도 우선)
    data_lines = _collect_data_lines(budget_start + 1, 60, use_break=True)
    raw_numbers = _extract_numbers(data_lines)

    # 2차 시도: 1차에서 데이터가 부족하면, break 없이 확장 탐색
    if len(raw_numbers) < 2:
        data_lines = _collect_data_lines(budget_start + 1, 80, use_break=False)
        raw_numbers = _extract_numbers(data_lines)

    # 헤더 구조: 2024결산 | 2025본예산 | 2025추경(A) | 2026요구안 | 2026본예산(B) | 증감(B-A) | 증감률
    if len(raw_numbers) >= 7:
        nums = raw_numbers[:7]
        result["budget_2024"] = _parse_token(nums[0])
        result["budget_2025"] = _parse_token(nums[1])
        result["budget_2025_sup"] = _parse_token(nums[2])
        result["budget_2026_req"] = _parse_token(nums[3])
        result["budget_2026"] = _parse_token(nums[4])
        result["change_amount"] = _parse_token(nums[5])
        result["change_rate"] = _parse_token(nums[6])
    elif len(raw_numbers) >= 5:
        nums = raw_numbers[:5]
        result["budget_2024"] = _parse_token(nums[0])
        result["budget_2025"] = _parse_token(nums[1])
        result["budget_2025_sup"] = _parse_token(nums[1])
        result["budget_2026"] = _parse_token(nums[2])
        result["change_amount"] = _parse_token(nums[3])
        result["change_rate"] = _parse_token(nums[4])
    elif len(raw_numbers) >= 2:
        result["budget_2026"] = _parse_token(raw_numbers[0])
        result["change_amount"] = _parse_token(raw_numbers[1]) if len(raw_numbers) > 1 else None

    return result


# ── 사업목적·내용 추출 ────────────────────────────────────

def extract_description(text: str) -> str | None:
    """
    텍스트에서 '사업목적·내용' 섹션을 추출합니다.
    유니코드 변이를 모두 처리합니다 (·, ･, ., -, 등).
    """
    lines = text.split("\n")
    desc_start = None

    for i, line in enumerate(lines):
        # 다양한 유니코드 가운데점/구분자 대응
        if re.search(r"사업목적\s*[·\uff65\.\-\s]*\s*내용", line):
            desc_start = i + 1
            break

    if desc_start is None:
        return None

    # "2) 사업개요" 또는 다음 번호 항목까지 수집
    desc_lines = []
    for i in range(desc_start, min(desc_start + 50, len(lines))):
        line = lines[i].strip()
        if not line:
            continue
        # 다음 섹션 시작 감지
        if re.match(r"^\d+\)\s", line) and "사업목적" not in line:
            break
        if re.match(r"^[가-힣]\.\s", line):
            break
        if "□사업근거" in line or "□사업 근거" in line:
            break
        desc_lines.append(line)

    if not desc_lines:
        return None

    return " ".join(desc_lines)


def extract_budget_by_table(pdf_path: str, local_start: int, local_end: int) -> dict:
    """pdfplumber를 사용하여 시각적 표에서 예산 데이터를 추출합니다.
    
    PyMuPDF의 텍스트 추출 순서 문제로 실패한 경우의 fallback입니다.
    '목명' 또는 '사업명' 열 헤더가 있는 표를 찾아 데이터를 파싱합니다.
    """
    result = {
        "budget_2024": None, "budget_2025": None, "budget_2025_sup": None,
        "budget_2026_req": None, "budget_2026": None,
        "change_amount": None, "change_rate": None,
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for pi in range(local_start, min(local_end + 1, len(pdf.pages))):
                tables = pdf.pages[pi].extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    # 헤더 행에 '목명' 또는 '사업명' 포함 확인
                    header_text = " ".join(str(c) for c in table[0] if c)
                    if "목명" not in header_text and "사업명" not in header_text:
                        continue
                    # 2024, 2026 등 연도 키워드 확인으로 총괄표인지 검증
                    all_text = " ".join(str(c) for row in table for c in row if c)
                    if "2026" not in all_text:
                        continue
                    
                    # 마지막 데이터 행 사용 (첫 행은 헤더)
                    data_row = table[-1]
                    # 셀에서 숫자 추출
                    values = []
                    for cell in data_row:
                        if cell is None or str(cell).strip() == "":
                            values.append("DASH")
                        else:
                            cell_str = str(cell).strip().replace("\n", " ")
                            if cell_str == "-" or cell_str == "":
                                values.append("DASH")
                            elif cell_str in ("순증", "순감"):
                                values.append(cell_str)
                            else:
                                # 숫자 추출
                                nums = re.findall(r"[△▽]?[\d,]+\.?\d*", cell_str)
                                if nums:
                                    values.append(nums[0])
                                else:
                                    pass  # 사업명 등 텍스트는 무시
                    
                    # 값 매핑 (첫 번째는 사업명이므로 제외하고 나머지)
                    def _pt(t):
                        if t == "DASH":
                            return None
                        return parse_number(t)
                    
                    if len(values) >= 7:
                        result["budget_2024"] = _pt(values[0])
                        result["budget_2025"] = _pt(values[1])
                        result["budget_2025_sup"] = _pt(values[2])
                        result["budget_2026_req"] = _pt(values[3])
                        result["budget_2026"] = _pt(values[4])
                        result["change_amount"] = _pt(values[5])
                        result["change_rate"] = _pt(values[6])
                    elif len(values) >= 5:
                        result["budget_2024"] = _pt(values[0])
                        result["budget_2025"] = _pt(values[1])
                        result["budget_2026"] = _pt(values[2])
                        result["change_amount"] = _pt(values[3])
                        result["change_rate"] = _pt(values[4])
                    
                    if result["budget_2026"] is not None:
                        return result
    except Exception:
        pass
    
    return result


# ── 메인 추출 로직 ────────────────────────────────────────

def extract_all_projects() -> pd.DataFrame:
    """모든 부처의 모든 사업을 추출하여 DataFrame으로 반환합니다."""

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    rows = []
    total = 0
    success_budget = 0
    success_desc = 0
    errors = []

    dept_list = index_data["부처별_사업목록"]

    for dept_name, dept_info in dept_list.items():
        pdf_path = os.path.join(RESOURCE_DIR, dept_info["파일명"])
        dept_start_page = dept_info["원본_시작페이지"]

        if not os.path.exists(pdf_path):
            print(f"  [SKIP] PDF 없음: {pdf_path}")
            continue

        doc = fitz.open(pdf_path)

        for proj in dept_info["사업목록"]:
            total += 1
            proj_name = proj["사업명"]
            local_start = proj["원본_시작페이지"] - dept_start_page
            local_end = proj["원본_끝페이지"] - dept_start_page

            try:
                text = extract_text_for_project(doc, local_start, local_end)

                # 예산 추출 (1차: PyMuPDF 텍스트 기반)
                budget = extract_budget_summary(text, proj_name)
                
                # 3차 fallback: pdfplumber 표 추출
                if budget["budget_2026"] is None:
                    budget = extract_budget_by_table(
                        pdf_path, local_start, local_end
                    )
                
                if budget["budget_2026"] is not None:
                    success_budget += 1

                # 사업내용 추출
                desc = extract_description(text)
                if desc:
                    success_desc += 1

                # 신규사업 판별: 2024·2025 예산이 모두 없고 2026만 있는 경우
                is_new = (
                    budget["budget_2024"] is None
                    and budget["budget_2025"] is None
                    and (budget["budget_2025_sup"] is None or budget["budget_2025_sup"] == 0)
                    and budget["budget_2026"] is not None
                )

                rows.append({
                    "dept_name": dept_name,
                    "project_no": proj["번호"],
                    "project_name": proj_name,
                    "page_start": proj["원본_시작페이지"],
                    "page_end": proj["원본_끝페이지"],
                    "budget_2024": budget["budget_2024"],
                    "budget_2025": budget["budget_2025"],
                    "budget_2025_sup": budget["budget_2025_sup"],
                    "budget_2026_req": budget["budget_2026_req"],
                    "budget_2026": budget["budget_2026"],
                    "change_amount": budget["change_amount"],
                    "change_rate": budget["change_rate"],
                    "is_new": is_new,
                    "description": desc,
                })
            except Exception as e:
                errors.append(f"  [{dept_name}] {proj_name}: {e}")
                rows.append({
                    "dept_name": dept_name,
                    "project_no": proj["번호"],
                    "project_name": proj_name,
                    "page_start": proj["원본_시작페이지"],
                    "page_end": proj["원본_끝페이지"],
                    "budget_2024": None,
                    "budget_2025": None,
                    "budget_2025_sup": None,
                    "budget_2026_req": None,
                    "budget_2026": None,
                    "change_amount": None,
                    "change_rate": None,
                    "is_new": False,
                    "description": None,
                })

        doc.close()
        print(f"  [{dept_name}] {dept_info['사업수']}개 사업 처리 완료")

    # 결과 요약
    print(f"\n{'='*60}")
    print(f"총 {total}개 사업 처리")
    print(f"  예산데이터 추출 성공: {success_budget}/{total} ({100*success_budget/total:.1f}%)")
    print(f"  사업내용 추출 성공: {success_desc}/{total} ({100*success_desc/total:.1f}%)")
    if errors:
        print(f"  에러 {len(errors)}건:")
        for e in errors[:10]:
            print(f"    {e}")
    print(f"{'='*60}")

    return pd.DataFrame(rows)


# ── CSV 저장 ──────────────────────────────────────────────

def save_csv(df: pd.DataFrame):
    """DataFrame을 CSV 파일로 저장합니다."""
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"\nCSV 저장 완료: {CSV_PATH} ({len(df)} rows)")


# ── SQLite DB 저장 ────────────────────────────────────────

def save_db(df: pd.DataFrame):
    """DataFrame을 SQLite DB에 저장하고 대시보드용 뷰를 생성합니다."""
    conn = sqlite3.connect(DB_PATH)

    # 메인 테이블
    df.to_sql("projects", conn, if_exists="replace", index=False)

    # 부처별 요약 뷰
    conn.execute("DROP VIEW IF EXISTS dept_summary")
    conn.execute("""
        CREATE VIEW dept_summary AS
        SELECT
            dept_name AS 부처명,
            COUNT(*) AS 사업수,
            SUM(COALESCE(budget_2025_sup, budget_2025, 0)) AS "2025_총예산_백만원",
            SUM(COALESCE(budget_2026, 0)) AS "2026_총예산_백만원",
            SUM(COALESCE(change_amount, 0)) AS 총증감액_백만원,
            SUM(CASE WHEN is_new = 1 THEN 1 ELSE 0 END) AS 신규사업수,
            SUM(CASE WHEN change_amount > 0 THEN change_amount ELSE 0 END) AS 증가총액_백만원,
            SUM(CASE WHEN change_amount < 0 THEN change_amount ELSE 0 END) AS 감소총액_백만원
        FROM projects
        GROUP BY dept_name
        ORDER BY "2026_총예산_백만원" DESC
    """)

    # 신규사업 뷰
    conn.execute("DROP VIEW IF EXISTS new_projects")
    conn.execute("""
        CREATE VIEW new_projects AS
        SELECT
            dept_name AS 부처명,
            project_name AS 사업명,
            budget_2026 AS "2026_예산_백만원",
            description AS 사업내용
        FROM projects
        WHERE is_new = 1
        ORDER BY budget_2026 DESC
    """)

    # 증감 분석 뷰
    conn.execute("DROP VIEW IF EXISTS budget_changes")
    conn.execute("""
        CREATE VIEW budget_changes AS
        SELECT
            dept_name AS 부처명,
            project_name AS 사업명,
            COALESCE(budget_2025_sup, budget_2025) AS "2025_예산",
            budget_2026 AS "2026_예산",
            change_amount AS 증감액,
            change_rate AS 증감률,
            CASE
                WHEN change_amount > 0 THEN '증가'
                WHEN change_amount < 0 THEN '감소'
                WHEN change_amount = 0 THEN '동결'
                ELSE '미확인'
            END AS 증감구분
        FROM projects
        WHERE budget_2026 IS NOT NULL
        ORDER BY change_amount DESC
    """)

    conn.commit()
    conn.close()
    print(f"SQLite DB 저장 완료: {DB_PATH}")


# ── 실행 ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("AIbudget - 전체 부처 예산사업 데이터 추출")
    print("=" * 60)

    df = extract_all_projects()
    save_csv(df)
    save_db(df)

    # 간단한 요약 출력
    print(f"\n[요약 통계]")
    print(f"  전체 사업 수: {len(df)}")
    print(f"  2026 예산 추출 성공: {df['budget_2026'].notna().sum()}")
    print(f"  신규 사업 수: {df['is_new'].sum()}")
    print(f"  사업내용 추출 성공: {df['description'].notna().sum()}")
    print(f"  2026 총 예산: {df['budget_2026'].sum():,.0f} 백만원")

    # 증감 분포
    has_change = df[df['change_amount'].notna()]
    if len(has_change) > 0:
        increased = has_change[has_change['change_amount'] > 0]
        decreased = has_change[has_change['change_amount'] < 0]
        frozen = has_change[has_change['change_amount'] == 0]
        print(f"  예산 증가 사업: {len(increased)} ({increased['change_amount'].sum():,.0f} 백만원)")
        print(f"  예산 감소 사업: {len(decreased)} ({decreased['change_amount'].sum():,.0f} 백만원)")
        print(f"  예산 동결 사업: {len(frozen)}")
