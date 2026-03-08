"""
extract_budget_raw.py — 예산 총괄표 추출 진단 스크립트
=======================================================
extract_all.py의 파싱 로직을 단계별로 노출하여 중간 상태를 CSV로 저장합니다.

출력 컬럼:
  부처명, 번호, 사업명, 페이지_시작, 페이지_끝
  총괄표_찾음, has_추경, has_요구
  서브앵커_라인       ← "목명"/"사업명" 단독행이 몇 번째 줄에서 발견됐는지
  수집라인            ← 필터 통과한 데이터 행들 ("|" 구분)
  추출숫자            ← raw_numbers 리스트 ("|" 구분)
  숫자개수            ← len(raw_numbers)
  매핑방법            ← "7열" / "6열A(추경)" / "6열B(요구)" / "5열" / "2열이하" / "fallback"
  budget_2024 ~ change_rate (최종 파싱값)
  총괄표_앞뒤_원문     ← 총괄표 섹션 전후 20줄 원문 (디버깅용)
"""

import json
import os
import re
import sys

import fitz  # PyMuPDF
import pandas as pd
from tqdm import tqdm

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCE_DIR = os.path.join(BASE_DIR, "resource", "budget_depts")
INDEX_PATH = os.path.join(RESOURCE_DIR, "meta", "00_사업목록_인덱스.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "extract_budget.csv")

os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)


# ── 헤더 키워드 (extract_all.py와 동일) ──────────────────
_HEADER_KEYWORDS = [
    "사업명", "결산", "예산", "본예산", "추경", "요구", "증감", "단위",
    "백만원", "(B-A)", "(A)", "(B)", "/A", "년", "조정",
    "목명", "목별", "계획", "정부안", "확정", "이관",
    "사업구조", "구조개편", "기능별", "내역사업",
    "현액", "집행액", "불용액", "이월액", "당초", "수정",
    "월말",
]


def _is_header_line(line: str) -> bool:
    for kw in _HEADER_KEYWORDS:
        if kw in line:
            return True
    return False


def _is_year_number(s: str) -> bool:
    s_clean = s.replace(",", "").replace("△", "").replace("▽", "")
    try:
        v = int(float(s_clean))
        return 2020 <= v <= 2029
    except (ValueError, OverflowError):
        return False


def parse_number(s):
    if s is None:
        return None
    s = s.strip()
    if s in ("-", "–", "―", "", "순증", "순감"):
        return None
    negative = False
    if s.startswith("△") or s.startswith("▽"):
        negative = True
        s = s[1:]
    s = s.replace(",", "").replace(" ", "").replace("%", "")
    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


# ── 진단 포함 파싱 함수 ───────────────────────────────────

def extract_budget_with_diagnostics(text: str, project_name: str) -> dict:
    """
    extract_all.py의 extract_budget_summary와 동일한 로직이지만
    중간 상태를 모두 반환합니다.
    """
    diag = {
        "총괄표_찾음": False,
        "총괄표_라인번호": None,
        "has_추경": False,
        "has_요구": False,
        "서브앵커_라인": None,
        "수집라인": [],
        "추출숫자": [],
        "숫자개수": 0,
        "매핑방법": "없음",
        "총괄표_원문": "",
        "budget_2024": None,
        "budget_2025": None,
        "budget_2025_sup": None,
        "budget_2026_req": None,
        "budget_2026": None,
        "change_amount": None,
        "change_rate": None,
    }

    lines = text.split("\n")

    # 총괄표 위치
    budget_start = None
    for i, line in enumerate(lines):
        if re.search(r"(예산|지출계획|예산안|지출계획안)\s*총괄표", line):
            budget_start = i
            break

    if budget_start is None:
        return diag

    diag["총괄표_찾음"] = True
    diag["총괄표_라인번호"] = budget_start
    # 총괄표 전후 원문 (40줄)
    raw_section = lines[max(0, budget_start - 2): min(budget_start + 40, len(lines))]
    diag["총괄표_원문"] = "\n".join(raw_section)

    # 열 구조 감지
    header_context = "\n".join(lines[budget_start: min(budget_start + 20, len(lines))])
    diag["has_추경"] = "추경" in header_context
    diag["has_요구"] = any(kw in header_context for kw in ["요구안", "요구"])

    # 사업명 숫자 토큰
    _name_numbers = set(re.findall(r"\d+", project_name))
    for _t in re.findall(r"[\d,]+\.?\d*", project_name):
        _cleaned = _t.replace(",", "")
        if _cleaned:
            _name_numbers.add(_cleaned)
    _name_key = re.sub(r"[\s\(\)（）]", "", project_name)

    def _collect_data_lines(start, end_offset, use_break):
        data_start = start
        anchor_line = None
        for i in range(start, min(start + end_offset, len(lines))):
            line = lines[i].strip()
            if use_break and "사업설명자료" in line:
                break
            if line in ("목명", "사업명"):
                data_start = i + 1
                anchor_line = i
                break

        collected = []
        for i in range(data_start, min(start + end_offset, len(lines))):
            line = lines[i].strip()
            if use_break and "사업설명자료" in line:
                break
            if use_break and line.startswith("□") and collected:
                break
            if line.startswith("○") or line.startswith("‧"):
                if collected:
                    break
                continue
            if _is_header_line(line):
                continue
            if not line:
                continue
            if re.match(r"^-\s*\d+\s*-$", line):
                continue
            if line.startswith("<") or line.startswith("※") or line.startswith("* "):
                continue
            if re.match(r"^\(\d[\d\-]*\)$", line):
                continue
            if not use_break:
                korean_chars = len(re.findall(r"[가-힣]", line))
                if korean_chars >= 15:
                    continue
            line_key = re.sub(r"[\s\(\)（）]", "", line)
            if len(_name_key) >= 6 and _name_key[:6] in line_key:
                continue
            if len(line_key) >= 4 and line_key in _name_key and re.search(r"\d", line_key):
                continue
            collected.append(line)
        return collected, anchor_line

    def _extract_numbers(d_lines):
        num_pattern = re.compile(r"[△▽]?[\d,]+\.?\d*|순증|순감|신규")
        nums = []
        for line in d_lines:
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

    def _pt(token):
        if token == "DASH":
            return None
        return parse_number(token)

    # 1차 시도
    data_lines, anchor = _collect_data_lines(budget_start + 1, 60, use_break=True)
    raw_numbers = _extract_numbers(data_lines)
    attempt = "1차(break)"

    # 2차 시도
    if len(raw_numbers) < 2:
        data_lines, anchor = _collect_data_lines(budget_start + 1, 80, use_break=False)
        raw_numbers = _extract_numbers(data_lines)
        attempt = "2차(nobreak)"

    diag["서브앵커_라인"] = anchor
    diag["수집라인"] = data_lines
    diag["추출숫자"] = raw_numbers
    diag["숫자개수"] = len(raw_numbers)

    # 열 매핑
    if len(raw_numbers) >= 7:
        nums = raw_numbers[:7]
        diag["매핑방법"] = f"7열({attempt})"
        diag["budget_2024"]    = _pt(nums[0])
        diag["budget_2025"]    = _pt(nums[1])
        diag["budget_2025_sup"]= _pt(nums[2])
        diag["budget_2026_req"]= _pt(nums[3])
        diag["budget_2026"]    = _pt(nums[4])
        diag["change_amount"]  = _pt(nums[5])
        diag["change_rate"]    = _pt(nums[6])
    elif len(raw_numbers) >= 6:
        nums = raw_numbers[:6]
        diag["budget_2024"] = _pt(nums[0])
        diag["budget_2025"] = _pt(nums[1])
        if diag["has_요구"] and not diag["has_추경"]:
            diag["매핑방법"] = f"6열B-요구({attempt})"
            diag["budget_2026_req"] = _pt(nums[2])
        else:
            diag["매핑방법"] = f"6열A-추경({attempt})"
            diag["budget_2025_sup"] = _pt(nums[2])
        diag["budget_2026"]   = _pt(nums[3])
        diag["change_amount"] = _pt(nums[4])
        diag["change_rate"]   = _pt(nums[5])
    elif len(raw_numbers) >= 5:
        nums = raw_numbers[:5]
        diag["매핑방법"] = f"5열({attempt})"
        diag["budget_2024"]   = _pt(nums[0])
        diag["budget_2025"]   = _pt(nums[1])
        diag["budget_2026"]   = _pt(nums[2])
        diag["change_amount"] = _pt(nums[3])
        diag["change_rate"]   = _pt(nums[4])
    elif len(raw_numbers) >= 2:
        diag["매핑방법"] = f"2열이하({attempt})"
        diag["budget_2026"]   = _pt(raw_numbers[0])
        diag["change_amount"] = _pt(raw_numbers[1]) if len(raw_numbers) > 1 else None
    else:
        diag["매핑방법"] = f"실패({attempt})"

    return diag


def extract_budget_by_table_raw(pdf_path, local_start, local_end):
    """pdfplumber 표 추출 — 원시 표 데이터도 반환."""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for pi in range(local_start, min(local_end + 1, len(pdf.pages))):
                tables = pdf.pages[pi].extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    header_text = " ".join(str(c) for c in table[0] if c)
                    if "목명" not in header_text and "사업명" not in header_text:
                        continue
                    all_text = " ".join(str(c) for row in table for c in row if c)
                    if "2026" not in all_text:
                        continue
                    # 원시 표 반환 (첫 번째 적합한 표)
                    return table
    except Exception:
        pass
    return None


# ── 메인 ─────────────────────────────────────────────────

def main():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    dept_list = index_data["부처별_사업목록"]
    rows = []

    all_projects = []
    for dept_name, dept_info in dept_list.items():
        for proj in dept_info["사업목록"]:
            all_projects.append((dept_name, dept_info, proj))

    print(f"총 {len(all_projects)}개 사업 진단 추출 시작...")

    for dept_name, dept_info, proj in tqdm(all_projects):
        pdf_path = os.path.join(RESOURCE_DIR, dept_info["파일명"])
        dept_start = dept_info["원본_시작페이지"]
        proj_name = proj["사업명"]
        local_start = proj["원본_시작페이지"] - dept_start
        local_end   = proj["원본_끝페이지"]   - dept_start

        row = {
            "부처명": dept_name,
            "번호": proj["번호"],
            "사업명": proj_name,
            "페이지_시작": proj["원본_시작페이지"],
            "페이지_끝":   proj["원본_끝페이지"],
            "총괄표_찾음": False,
            "총괄표_라인번호": None,
            "has_추경": False,
            "has_요구": False,
            "서브앵커_라인": None,
            "수집라인": "",
            "추출숫자": "",
            "숫자개수": 0,
            "매핑방법": "없음",
            "budget_2024": None,
            "budget_2025": None,
            "budget_2025_sup": None,
            "budget_2026_req": None,
            "budget_2026": None,
            "change_amount": None,
            "change_rate": None,
            "총괄표_원문": "",
            "fallback_표구조": "",
        }

        if not os.path.exists(pdf_path):
            row["매핑방법"] = "PDF없음"
            rows.append(row)
            continue

        try:
            doc = fitz.open(pdf_path)
            text = ""
            for p_idx in range(local_start, min(local_end + 1, len(doc))):
                text += doc[p_idx].get_text() + "\n"
            doc.close()

            diag = extract_budget_with_diagnostics(text, proj_name)

            row.update({
                "총괄표_찾음":    diag["총괄표_찾음"],
                "총괄표_라인번호": diag["총괄표_라인번호"],
                "has_추경":       diag["has_추경"],
                "has_요구":       diag["has_요구"],
                "서브앵커_라인":  diag["서브앵커_라인"],
                "수집라인":       " | ".join(diag["수집라인"]),
                "추출숫자":       " | ".join(str(n) for n in diag["추출숫자"]),
                "숫자개수":       diag["숫자개수"],
                "매핑방법":       diag["매핑방법"],
                "budget_2024":    diag["budget_2024"],
                "budget_2025":    diag["budget_2025"],
                "budget_2025_sup":diag["budget_2025_sup"],
                "budget_2026_req":diag["budget_2026_req"],
                "budget_2026":    diag["budget_2026"],
                "change_amount":  diag["change_amount"],
                "change_rate":    diag["change_rate"],
                "총괄표_원문":    diag["총괄표_원문"],
            })

            # pdfplumber fallback이 필요한 경우 표 원시 구조도 기록
            if diag["budget_2026"] is None:
                raw_table = extract_budget_by_table_raw(pdf_path, local_start, local_end)
                if raw_table:
                    # 표를 읽기 쉬운 텍스트로 변환
                    table_str = "\n".join(
                        " | ".join(str(c).replace("\n", "↵") if c else "" for c in r)
                        for r in raw_table
                    )
                    row["fallback_표구조"] = table_str
                    row["매핑방법"] += " → fallback필요"

        except Exception as e:
            row["매핑방법"] = f"에러: {e}"

        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"\n저장 완료: {OUTPUT_PATH}")
    print(f"총 {len(df)}건")
    print(f"\n[매핑방법 분포]")
    print(df["매핑방법"].value_counts().to_string())
    print(f"\n[budget_2026 추출 성공률]")
    print(f"  성공: {df['budget_2026'].notna().sum()} / {len(df)}")
    print(f"  실패: {df['budget_2026'].isna().sum()}")
    if df["budget_2026"].isna().any():
        failed = df[df["budget_2026"].isna()][["부처명", "사업명", "매핑방법", "숫자개수"]]
        print(failed.to_string(index=False))


if __name__ == "__main__":
    main()
