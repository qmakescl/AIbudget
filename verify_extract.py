"""
verify_extract.py — 2026 정부 AI 예산 PDF 재추출 및 검증 스크립트

추출 전략:
  1단계: pdfplumber 표 추출 (셀 경계 보존 → 열 밀림 방지)
  2단계: PyMuPDF 텍스트 파싱 1차 (60줄, break: 사업설명자료)
  3단계: PyMuPDF 텍스트 파싱 2차 (80줄, break 해제)

출력:
  data/budget_data_verified.csv   — 재추출 결과 (기존 스키마 호환)
  data/extraction_audit.csv       — 추출 방법 및 검증 플래그
  report/extraction_validation_report.md — 검증 리포트
"""

import json
import re
from pathlib import Path

import pandas as pd
import pdfplumber
import fitz  # PyMuPDF

# ─── 경로 설정 ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
PDF_DIR = BASE_DIR / "resource" / "budget_depts"
INDEX_FILE = PDF_DIR / "meta" / "00_사업목록_인덱스.json"
OUT_CSV = BASE_DIR / "data" / "budget_data_verified.csv"
AUDIT_CSV = BASE_DIR / "data" / "extraction_audit.csv"
REPORT_MD = BASE_DIR / "report" / "extraction_validation_report.md"

# ─── 상수 ────────────────────────────────────────────────────────────────────

# 예산 총괄표 제목 탐지 패턴
_TABLE_TITLE_RE = re.compile(
    r"(가\.\s*)?(□\s*)?(예산|지출계획|예산안|지출계획안)\s*총괄표"
)

# 숫자 + 마커 패턴
# △(U+25B3) ▽(U+25BD): 일반 삼각형 — 대부분 부처
# ▵(U+25B5): 소삼각형 — 경찰청·방위사업청 등 일부 PDF
# ∆(U+2206): 증분기호 — 산업통상자원부 등 일부 PDF
_NUM_RE = re.compile(r"[△▽▵∆]?[\d,]+\.?\d*|순증|순감|신규")

# 헤더 행에서 건너뛸 키워드 (메타 행 필터)
_HEADER_KEYWORDS = {
    "사업명", "목명", "결산", "예산", "본예산", "추경", "요구", "증감", "단위",
    "백만원", "(B-A)", "(A)", "(B)", "/A", "2024", "2025", "2026", "조정",
    "목별", "계획", "정부안", "확정", "이관", "구조", "기능별", "내역",
    "현액", "집행액", "불용액", "이월액", "당초", "수정", "년도",
}

# 연도 숫자 무시 패턴 (사업명 내 연도값)
_YEAR_RE = re.compile(r"^20[12]\d$")

# ─── 숫자 파싱 ────────────────────────────────────────────────────────────────

def parse_number(s) -> float | None:
    """예산 숫자 문자열 → float. 대시·마커는 None 반환."""
    if s is None:
        return None
    s = str(s).strip().replace(" ", "")
    if not s or s in ("-", "–", "―", "—", "순증", "순감", "신규", "-"):
        return None
    negative = False
    # △(U+25B3) ▽(U+25BD) ▵(U+25B5 소삼각형) ∆(U+2206 증분기호) → 음수
    if s[0] in ("△", "▽", "▵", "∆"):
        negative = True
        s = s[1:]
    s = s.replace(",", "").rstrip("%")
    try:
        v = float(s)
        return -v if negative else v
    except ValueError:
        return None


def is_marker(s) -> bool:
    """순증/순감/신규/대시 마커 여부."""
    if s is None:
        return False
    s = str(s).strip()
    return s in ("-", "–", "―", "—", "순증", "순감", "신규")


# ─── 열 구조 감지 ─────────────────────────────────────────────────────────────

def detect_column_structure(header_rows: list[list]) -> dict:
    """
    pdfplumber 표의 헤더 행들로부터 각 열의 의미를 감지.
    반환: {필드명: 열인덱스} — 없는 열은 포함되지 않음.
    """
    # 헤더의 모든 셀 텍스트를 열별로 합산
    if not header_rows:
        return {}

    max_cols = max(len(r) for r in header_rows)
    col_texts = [""] * max_cols
    for row in header_rows:
        for i, cell in enumerate(row):
            if cell:
                col_texts[i] += str(cell).strip() + " "

    mapping = {}
    for i, text in enumerate(col_texts):
        t = text.strip()
        if not t:
            continue
        # 증감비율: \(B-A\)/A (괄호 이스케이프 필수) 且 "증감" 없음, 또는 비율 키워드
        # 주의: (B-A)/A 를 un-escaped로 쓰면 regex 그룹으로 해석되어 매핑 실패
        if (re.search(r"\(B-A\)/A", t) and "증감" not in t) or re.search(r"증감.*률|비율(?!.*증감)", t):
            mapping.setdefault("change_rate", i)
        elif re.search(r"B-A|증감", t):
            mapping.setdefault("change_amount", i)
        elif re.search(r"2024|결산", t):
            mapping.setdefault("budget_2024", i)
        elif re.search(r"추경", t):
            mapping.setdefault("budget_2025_sup", i)
        elif re.search(r"(2025|당초|본예산).*(A|확정)|본예산.*2025", t, re.S):
            mapping.setdefault("budget_2025", i)
        elif re.search(r"본예산|계획", t) and "budget_2025" not in mapping and "2026" not in t:
            mapping.setdefault("budget_2025", i)
        elif re.search(r"요구|요청", t):
            mapping.setdefault("budget_2026_req", i)
        elif re.search(r"(조정|본예산|확정).*(B)|2026.*(B)|정부안", t, re.S):
            mapping.setdefault("budget_2026", i)
        elif re.search(r"2026", t) and "budget_2026" not in mapping:
            mapping.setdefault("budget_2026", i)

    return mapping


def is_budget_summary_table(table: list[list]) -> bool:
    """pdfplumber 표가 예산 총괄표인지 판별."""
    if not table or len(table) < 2:
        return False
    flat = " ".join(str(c) for row in table for c in row if c)
    has_name = bool(re.search(r"사업명|목명", flat))
    has_2026 = "2026" in flat
    has_budget = bool(re.search(r"예산|결산|증감", flat))
    return has_name and has_2026 and has_budget


# ─── pdfplumber 1단계 추출 ────────────────────────────────────────────────────

def extract_via_pdfplumber(pdf_path: Path, local_start: int, local_end: int) -> dict | None:
    """
    pdfplumber로 표를 직접 추출. 열 경계가 보존되어 열 밀림 없음.
    반환: 예산 딕셔너리 or None
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total = len(pdf.pages)
            for pi in range(local_start, min(local_end + 1, total)):
                tables = pdf.pages[pi].extract_tables()
                for table in tables:
                    if not is_budget_summary_table(table):
                        continue
                    return _parse_plumber_table(table)
    except Exception as e:
        pass
    return None


def _parse_plumber_table(table: list[list]) -> dict | None:
    """
    pdfplumber 표 → 예산 딕셔너리.
    헤더 행과 데이터 행을 분리한 뒤 열 의미 매핑.
    """
    # 데이터 행: 숫자 또는 "-" 가 가장 많은 행을 선택 (마지막 헤더 이후 첫 번째)
    header_rows = []
    data_rows = []
    bullet_rows = []   # ○로 시작하나 숫자 비율은 충분한 행 (fallback용)
    found_header_end = False

    for row in table:
        cells = [str(c).strip() if c else "" for c in row]
        # 행 내 숫자셀 비율로 헤더/데이터 구분
        numeric_count = sum(1 for c in cells if parse_number(c) is not None or is_marker(c))
        total_nonempty = sum(1 for c in cells if c)
        if total_nonempty == 0:
            continue

        ratio = numeric_count / total_nonempty if total_nonempty else 0
        if ratio >= 0.5 and found_header_end:
            first = cells[0] if cells else ""
            if re.match(r"^[○·]", first):
                # 소계 행 후보로 따로 보관
                bullet_rows.append(cells)
                continue
            data_rows.append(cells)
        else:
            header_rows.append(cells)
            if re.search(r"2026|증감|정부안", " ".join(cells)):
                found_header_end = True

    # ○ 필터로 인해 data_rows가 비면, bullet_rows를 fallback으로 사용
    # (단일 총괄 행이 ○로 시작하는 경우 — 예: 과학기술정보통신부 기금사업)
    if not data_rows and bullet_rows:
        data_rows = bullet_rows

    if not data_rows:
        return None

    mapping = detect_column_structure(header_rows)
    if not mapping:
        return None

    # 주행: 전체 합계 행 (사업명 열이 비어있거나 "합계", 또는 첫 번째 데이터 행)
    # 사업 총괄표에서는 보통 첫 번째 데이터 행이 총괄값
    target_row = data_rows[0]
    for row in data_rows:
        if row[0] in ("", None, "합계", "소계"):
            target_row = row
            break

    def get(field):
        idx = mapping.get(field)
        if idx is None or idx >= len(target_row):
            return None
        return parse_number(target_row[idx])

    def get_raw(field):
        idx = mapping.get(field)
        if idx is None or idx >= len(target_row):
            return None
        return str(target_row[idx]).strip() if target_row[idx] else None

    # 2025 실제예산 결정
    b2025 = get("budget_2025")
    b2025_sup = get("budget_2025_sup")
    # 추경열 없이 (A) 표기된 경우 budget_2025가 이미 추경
    if "budget_2025_sup" not in mapping and b2025 is not None:
        b2025_sup = b2025  # 6열 구조: 본예산(A)가 실질 추경 기준

    # 신규 마커 확인: 2024와 2025 모두 "-" 또는 None이어야 신규 (OR → AND)
    raw_rate = get_raw("change_rate")
    raw_amount = get_raw("change_amount")
    no_2024 = is_marker(get_raw("budget_2024")) or get("budget_2024") is None
    no_2025 = is_marker(get_raw("budget_2025")) or get("budget_2025") is None
    is_new_marker = no_2024 and no_2025
    new_keywords = {"순증", "신규"}
    is_new_rate = raw_rate in new_keywords if raw_rate else False
    is_new_amount = raw_amount in new_keywords if raw_amount else False

    result = {
        "budget_2024": get("budget_2024"),
        "budget_2025": b2025,
        "budget_2025_sup": b2025_sup,
        "budget_2026_req": get("budget_2026_req"),
        "budget_2026": get("budget_2026"),
        "change_amount": get("change_amount"),
        "change_rate": get("change_rate"),
        "_column_count": len(target_row),
        "_mapping": mapping,
        "_is_new_marker": is_new_marker or is_new_rate or is_new_amount,
    }
    return result if result["budget_2026"] is not None else None


# ─── PyMuPDF 2~3단계 추출 ────────────────────────────────────────────────────

def extract_via_pymupdf(pdf_path: Path, local_start: int, local_end: int) -> dict | None:
    """PyMuPDF 텍스트 기반 추출 (2단계: break, 3단계: no-break)."""
    try:
        doc = fitz.open(pdf_path)
        lines = _collect_text_lines(doc, local_start, local_end)
        doc.close()
    except Exception:
        return None

    # 총괄표 시작점 탐지
    budget_start = None
    for i, line in enumerate(lines):
        if _TABLE_TITLE_RE.search(line):
            budget_start = i
            break

    if budget_start is None:
        return None

    # 2단계: 사업설명자료 break, 60줄
    result = _parse_text_lines(lines, budget_start + 1, 60, use_break=True)
    if result and result.get("budget_2026") is not None:
        result["_method"] = "pymupdf_pass1"
        return result

    # 3단계: break 해제, 80줄
    result = _parse_text_lines(lines, budget_start + 1, 80, use_break=False)
    if result and result.get("budget_2026") is not None:
        result["_method"] = "pymupdf_pass2"
        return result

    return None


def _collect_text_lines(doc, local_start: int, local_end: int) -> list[str]:
    """PyMuPDF에서 지정 페이지 범위 텍스트를 줄 단위로 수집."""
    lines = []
    for pi in range(local_start, min(local_end + 1, len(doc))):
        text = doc[pi].get_text("text")
        lines.extend(text.splitlines())
    return lines


def _parse_text_lines(lines: list[str], start: int, window: int, use_break: bool) -> dict | None:
    """지정 줄 범위에서 숫자를 추출하여 예산값 매핑."""
    nums = []
    is_new_marker = False

    for i, line in enumerate(lines[start: start + window]):
        stripped = line.strip()

        # 종료 조건
        if use_break:
            if re.search(r"나\.\s*사업설명자료", stripped):
                break
        # □ 기능별 이후 하위표 혼입 방지
        if re.match(r"□\s*(기능별|내역사업)", stripped):
            break

        # 헤더 키워드 포함 행 건너뜀
        if any(kw in stripped for kw in _HEADER_KEYWORDS):
            continue

        # 한글 15자 이상 → 설명 문장, 건너뜀 (3단계 확장 탐색 시)
        if not use_break and len(re.findall(r"[가-힣]", stripped)) >= 15:
            continue

        # 페이지 번호 행 건너뜀 (예: "- 971 -")
        if re.match(r"^-\s*\d+\s*-$", stripped):
            continue

        # 사업코드 행 건너뜀 (예: "(2047-500)", "(360-05)")
        if re.match(r"^\(\d[\d\-]*\)$", stripped):
            continue

        # 꺾쇠·주석 메타 행 건너뜀
        if stripped.startswith(("※", "< ", "*")):
            continue

        # 대시 단독 행 → DASH 마커
        if stripped in ("-", "–", "―", "—"):
            nums.append("DASH")
            continue

        # ○, · 접두어 행 → 소계/내역, 건너뜀
        if re.match(r"^[○·]", stripped):
            continue

        # 숫자/마커 추출
        found = _NUM_RE.findall(stripped)
        for f in found:
            if _YEAR_RE.match(f.replace(",", "")):
                continue
            if f in ("순증", "순감", "신규"):
                nums.append(f)
                is_new_marker = True
            else:
                nums.append(f)

    # 최소 6개 이상 수치가 있어야 매핑 시도
    if len(nums) < 6:
        return None

    return _map_text_nums(nums, is_new_marker)


def _map_text_nums(nums: list, is_new_marker: bool) -> dict:
    """
    텍스트 파싱으로 얻은 숫자/마커 목록 → 예산 딕셔너리.

    예산 총괄표 열 순서 (7열 기준):
      [0] 2024결산
      [1] 2025본예산
      [2] 2025추경(A)    ← 없으면 6열 구조
      [3] 2026요구안
      [4] 2026본예산(B)
      [5] 증감액(B-A)
      [6] 증감률

    DASH 마커 → None, 순증/순감/신규 → None (신규 플래그 처리)
    """
    parsed = []
    for n in nums:
        if n == "DASH":
            parsed.append(None)
        elif n in ("순증", "순감", "신규"):
            parsed.append(None)
        else:
            parsed.append(parse_number(n))

    n = len(parsed)

    if n >= 7:
        # 7열 구조
        b2024 = parsed[0]
        b2025 = parsed[1]
        b2025_sup = parsed[2]
        b2026_req = parsed[3]
        b2026 = parsed[4]
        change_amt = parsed[5]
        change_rate = parsed[6]
    elif n == 6:
        # 6열 구조 (추경 없음): 2024, 본예산(A), 요구, 확정(B), 증감, 비율
        b2024 = parsed[0]
        b2025 = parsed[1]
        b2025_sup = parsed[1]  # 6열에선 본예산=추경
        b2026_req = parsed[2]
        b2026 = parsed[3]
        change_amt = parsed[4]
        change_rate = parsed[5]
    else:
        # 값이 부족한 경우 — budget_2026만 추출 시도
        b2024 = b2025 = b2025_sup = b2026_req = None
        b2026 = parsed[-3] if n >= 3 else None
        change_amt = parsed[-2] if n >= 2 else None
        change_rate = parsed[-1] if n >= 1 else None

    return {
        "budget_2024": b2024,
        "budget_2025": b2025,
        "budget_2025_sup": b2025_sup,
        "budget_2026_req": b2026_req,
        "budget_2026": b2026,
        "change_amount": change_amt,
        "change_rate": change_rate,
        "_column_count": n,
        "_is_new_marker": is_new_marker,
        "_method": "pymupdf",
    }


# ─── 사업설명 추출 ────────────────────────────────────────────────────────────

# "사업목적·내용" 헤더 줄 탐지 — 다양한 유니코드 구분자 대응
# ·(U+00B7 가운데점) ･(U+FF65 반각) .(온점) -(하이픈) 공백 등
_DESC_ANCHOR_RE = re.compile(r"사업목적\s*[·･\uff65\.\-\s]*\s*내용")

# 다음 섹션 시작 → 수집 중단
_DESC_STOP_RE = re.compile(
    r"^2\)\s|^[가-하]\.\s|^□\s*사업근거|^□\s*사업 근거"
)


def extract_description(pdf_path: Path, local_start: int, local_end: int) -> str:
    """
    사업목적·내용 섹션 텍스트 추출.
    extract_all.py 방식 계승: '사업목적·내용' 헤더를 찾아 다음 줄부터 수집.
    """
    try:
        doc = fitz.open(pdf_path)
        lines = _collect_text_lines(doc, local_start, local_end)
        doc.close()
    except Exception:
        return ""

    desc_start = None
    for i, line in enumerate(lines):
        if _DESC_ANCHOR_RE.search(line.strip()):
            desc_start = i + 1
            break

    if desc_start is None:
        return ""

    desc_lines = []
    for line in lines[desc_start: desc_start + 50]:
        stripped = line.strip()
        if not stripped:
            continue
        # 다음 섹션 감지
        if _DESC_STOP_RE.search(stripped):
            break
        # "□사업근거" 등 박스 항목
        if stripped.startswith("□") and desc_lines:
            break
        # 페이지 번호 건너뜀
        if re.match(r"^-\s*\d+\s*-$", stripped):
            continue
        desc_lines.append(stripped)
        if len(desc_lines) >= 30:
            break

    return " ".join(desc_lines)


# ─── 교차 검증 ────────────────────────────────────────────────────────────────

def cross_validate(r_plumber: dict | None, r_pymupdf: dict | None) -> dict:
    """
    pdfplumber와 PyMuPDF 결과 교차 검증.
    pdfplumber 결과를 우선. 불일치 시 플래그.
    """
    if r_plumber and r_pymupdf:
        # budget_2026 비교 (오차 ±1)
        p = r_plumber.get("budget_2026")
        m = r_pymupdf.get("budget_2026")
        if p is not None and m is not None and abs(p - m) > 1:
            result = dict(r_plumber)
            result["_cross_validation"] = f"MISMATCH(plumber={p},pymupdf={m})"
            result["_method"] = "pdfplumber"
            return result
        result = dict(r_plumber)
        result["_cross_validation"] = "MATCH"
        result["_method"] = "pdfplumber"
        return result
    elif r_plumber:
        result = dict(r_plumber)
        result["_cross_validation"] = "SINGLE_PLUMBER"
        result["_method"] = "pdfplumber"
        return result
    elif r_pymupdf:
        result = dict(r_pymupdf)
        result["_cross_validation"] = "SINGLE_PYMUPDF"
        return result
    else:
        return {
            "budget_2024": None, "budget_2025": None, "budget_2025_sup": None,
            "budget_2026_req": None, "budget_2026": None,
            "change_amount": None, "change_rate": None,
            "_column_count": 0, "_is_new_marker": False,
            "_method": "FAILED", "_cross_validation": "FAILED",
        }


# ─── 자동 검증 ────────────────────────────────────────────────────────────────

def validate_record(rec: dict) -> list[str]:
    """
    단일 레코드 검증. 플래그 리스트 반환.
    V1 예산값 존재, V2 산술 일치, V3 비율 일치,
    V4 신규 일관성, V5 비율 범위, V6 음수 예산
    """
    flags = []

    b2026 = rec.get("budget_2026")
    b2025 = rec.get("budget_2025")
    b2025_sup = rec.get("budget_2025_sup")
    change_amt = rec.get("change_amount")
    change_rate = rec.get("change_rate")
    is_new = rec.get("is_new", False)

    # V1: budget_2026 존재
    if b2026 is None:
        flags.append("V1:NO_BUDGET_2026")
        return flags  # 이후 검증 불가

    # 실제 2025 기준 예산 (비율/증감 계산 기준)
    actual_2025 = b2025_sup if b2025_sup is not None else b2025

    # V2: 산술 일치 (신규사업 제외)
    if not is_new and actual_2025 is not None and change_amt is not None:
        expected = b2026 - actual_2025
        if abs(expected - change_amt) > 1:
            flags.append(f"V2:ARITHMETIC_MISMATCH(expected={expected:.0f},got={change_amt:.0f})")

    # V3: 증감비율 일치
    if not is_new and actual_2025 and actual_2025 != 0 and change_rate is not None:
        expected_rate = (b2026 - actual_2025) / actual_2025 * 100
        if abs(expected_rate - change_rate) > 0.5:
            flags.append(f"V3:RATE_MISMATCH(expected={expected_rate:.1f}%,got={change_rate:.1f}%)")

    # V4: 신규 일관성
    if is_new:
        if b2025 is not None and b2025 > 0:
            flags.append("V4:NEW_BUT_HAS_2025_BUDGET")
        if rec.get("budget_2024") is not None:
            flags.append("V4:NEW_BUT_HAS_2024_BUDGET")

    # V5: 비율 범위 (금액값 혼입 감지)
    if change_rate is not None:
        if change_rate < -100 or change_rate > 50000:
            flags.append(f"V5:RATE_OUT_OF_RANGE({change_rate})")

    # V6: 음수 예산
    for field, val in [("budget_2024", rec.get("budget_2024")),
                       ("budget_2025", b2025),
                       ("budget_2026", b2026)]:
        if val is not None and val < 0:
            flags.append(f"V6:NEGATIVE_{field.upper()}({val})")

    return flags


# ─── 신규사업 판별 ────────────────────────────────────────────────────────────

def determine_is_new(rec: dict) -> bool:
    """신규사업 여부 결정."""
    b2024 = rec.get("budget_2024")
    b2025 = rec.get("budget_2025")
    b2025_sup = rec.get("budget_2025_sup")
    marker = rec.get("_is_new_marker", False)

    no_prior = (
        (b2024 is None) and
        (b2025 is None or b2025 == 0) and
        (b2025_sup is None or b2025_sup == 0)
    )
    return no_prior or marker


# ─── 단일 프로젝트 추출 ──────────────────────────────────────────────────────

def extract_project(
    pdf_path: Path,
    dept_start_page: int,  # 원본 시작페이지 (1-indexed)
    proj_start_page: int,  # 원본 프로젝트 시작 (1-indexed)
    proj_end_page: int,    # 원본 프로젝트 끝 (1-indexed)
) -> tuple[dict, str, str]:
    """
    단일 프로젝트 예산 추출.
    반환: (예산 딕셔너리, 사업설명, 추출방법)
    """
    # 0-indexed local 페이지 변환
    local_start = proj_start_page - dept_start_page
    local_end = proj_end_page - dept_start_page
    local_start = max(local_start, 0)

    # 1단계: pdfplumber
    r_plumber = extract_via_pdfplumber(pdf_path, local_start, local_end)

    # 2~3단계: PyMuPDF
    r_pymupdf = extract_via_pymupdf(pdf_path, local_start, local_end)

    # 교차 검증 및 통합
    result = cross_validate(r_plumber, r_pymupdf)

    # 신규사업 판별
    result["is_new"] = determine_is_new(result)

    # 신규사업이면 change_amount = budget_2026 (기존 누락 수정)
    if result["is_new"] and result.get("change_amount") is None:
        result["change_amount"] = result.get("budget_2026")

    # 사업설명 추출
    description = extract_description(pdf_path, local_start, local_end)

    method = result.get("_method", "FAILED")
    return result, description, method


# ─── 메인 추출 루프 ───────────────────────────────────────────────────────────

def load_index() -> dict:
    with open(INDEX_FILE, encoding="utf-8") as f:
        return json.load(f)


def run_extraction(pilot_depts: list[str] | None = None) -> tuple[list, list]:
    """
    전체 또는 파일럿 부처 추출 실행.
    pilot_depts: None이면 전체 41개 부처.
    반환: (records, audits)
    """
    index = load_index()
    dept_map = index["부처별_사업목록"]

    depts = pilot_depts if pilot_depts else list(dept_map.keys())

    records = []
    audits = []
    total = sum(dept_map[d]["사업수"] for d in depts if d in dept_map)
    done = 0

    # 부처별 변이 카탈로그
    variation_catalog = {}

    for dept_name in depts:
        if dept_name not in dept_map:
            print(f"[SKIP] {dept_name} — 인덱스에 없음")
            continue

        dept_info = dept_map[dept_name]
        pdf_path = PDF_DIR / dept_info["파일명"]
        dept_start_page = dept_info["원본_시작페이지"]

        if not pdf_path.exists():
            print(f"[MISSING] {pdf_path}")
            continue

        dept_catalog = {
            "header_format": set(),
            "column_counts": set(),
            "new_markers": set(),
        }

        for proj in dept_info["사업목록"]:
            proj_no = proj["번호"]
            proj_name = proj["사업명"]
            proj_start = proj["원본_시작페이지"]
            proj_end = proj["원본_끝페이지"]

            try:
                result, description, method = extract_project(
                    pdf_path, dept_start_page, proj_start, proj_end
                )
            except Exception as e:
                print(f"  [ERROR] {dept_name} / {proj_name}: {e}")
                result = {
                    "budget_2024": None, "budget_2025": None, "budget_2025_sup": None,
                    "budget_2026_req": None, "budget_2026": None,
                    "change_amount": None, "change_rate": None,
                    "is_new": False, "_method": "EXCEPTION",
                    "_cross_validation": f"ERROR:{e}", "_column_count": 0,
                }
                description = ""
                method = "EXCEPTION"

            flags = validate_record(result)

            # 레코드
            rec = {
                "dept_name": dept_name,
                "project_no": proj_no,
                "project_name": proj_name,
                "page_start": proj_start,
                "page_end": proj_end,
                "budget_2024": result.get("budget_2024"),
                "budget_2025": result.get("budget_2025"),
                "budget_2025_sup": result.get("budget_2025_sup"),
                "budget_2026_req": result.get("budget_2026_req"),
                "budget_2026": result.get("budget_2026"),
                "change_amount": result.get("change_amount"),
                "change_rate": result.get("change_rate"),
                "is_new": result.get("is_new", False),
                "description": description,
            }
            records.append(rec)

            # 감사 레코드
            audit = {
                "dept_name": dept_name,
                "project_no": proj_no,
                "project_name": proj_name,
                "extraction_method": method,
                "column_count": result.get("_column_count", 0),
                "cross_validation": result.get("_cross_validation", ""),
                "validation_flags": "|".join(flags) if flags else "OK",
            }
            audits.append(audit)

            # 카탈로그 업데이트
            dept_catalog["column_counts"].add(result.get("_column_count", 0))
            if result.get("_is_new_marker"):
                dept_catalog["new_markers"].add("marker")

            done += 1
            status = "✓" if not flags else f"⚠ {','.join(f.split(':')[0] for f in flags)}"
            print(f"  [{done}/{total}] {dept_name} / {proj_name[:30]} — {method} {status}")

        variation_catalog[dept_name] = dept_catalog

    return records, audits, variation_catalog


# ─── 리포트 생성 ──────────────────────────────────────────────────────────────

def generate_report(records: list, audits: list, variation_catalog: dict):
    """검증 리포트 Markdown 생성."""
    df = pd.DataFrame(records)
    df_audit = pd.DataFrame(audits)

    total = len(df)
    extracted = int(df["budget_2026"].notna().sum())
    new_count = int(df["is_new"].sum())
    arithmetic_ok = int((df_audit["validation_flags"] == "OK").sum())
    v2_fail = int(df_audit["validation_flags"].str.contains("V2", na=False).sum())
    v3_fail = int(df_audit["validation_flags"].str.contains("V3", na=False).sum())
    v5_fail = int(df_audit["validation_flags"].str.contains("V5", na=False).sum())

    total_2026 = df["budget_2026"].sum()
    total_2025 = df["budget_2025_sup"].fillna(df["budget_2025"]).sum()
    net_change = total_2026 - total_2025

    # 추출 방법별 통계
    method_counts = df_audit["extraction_method"].value_counts().to_dict()

    # 부처별 요약
    dept_summary = (
        df_audit.groupby("dept_name")
        .apply(lambda g: pd.Series({
            "사업수": len(g),
            "OK": (g["validation_flags"] == "OK").sum(),
            "경고": (g["validation_flags"] != "OK").sum(),
        }))
        .reset_index()
    )

    # 플래그된 항목
    flagged = df_audit[df_audit["validation_flags"] != "OK"][
        ["dept_name", "project_name", "extraction_method", "validation_flags"]
    ]

    lines = [
        "# 예산 데이터 재추출 검증 리포트",
        "",
        f"> 생성일: 2026-03-09 | 추출 방법: pdfplumber(1차) + PyMuPDF(2~3차)",
        "",
        "---",
        "",
        "## 1. 전체 통계",
        "",
        f"| 항목 | 값 |",
        f"|------|---|",
        f"| 총 사업수 | {total}건 |",
        f"| budget_2026 추출 성공 | {extracted}건 ({extracted/total*100:.1f}%) |",
        f"| 신규사업 | {new_count}건 ({new_count/total*100:.1f}%) |",
        f"| 검증 전체 통과 (OK) | {arithmetic_ok}건 ({arithmetic_ok/total*100:.1f}%) |",
        f"| V2 산술 불일치 | {v2_fail}건 |",
        f"| V3 비율 불일치 | {v3_fail}건 |",
        f"| V5 비율 범위 이상 | {v5_fail}건 |",
        f"| 2026 총 예산 (백만원) | {total_2026:,.0f} |",
        f"| 2025 총 예산 (백만원) | {total_2025:,.0f} |",
        f"| 순증감 (백만원) | {net_change:+,.0f} |",
        "",
        "### 추출 방법 분포",
        "",
        "| 방법 | 건수 |",
        "|------|-----|",
    ]
    for m, c in sorted(method_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {m} | {c} |")

    lines += [
        "",
        "---",
        "",
        "## 2. 부처별 요약",
        "",
        "| 부처 | 사업수 | OK | 경고 |",
        "|------|------|------|------|",
    ]
    for _, row in dept_summary.iterrows():
        lines.append(f"| {row['dept_name']} | {row['사업수']} | {row['OK']} | {row['경고']} |")

    lines += [
        "",
        "---",
        "",
        "## 3. 검증 경고/실패 항목",
        "",
        "| 부처 | 사업명 | 추출방법 | 플래그 |",
        "|------|------|------|------|",
    ]
    for _, row in flagged.iterrows():
        name = str(row["project_name"])[:30]
        flags = str(row["validation_flags"])[:60]
        lines.append(f"| {row['dept_name']} | {name} | {row['extraction_method']} | {flags} |")

    lines += [
        "",
        "---",
        "",
        "## 4. 부처별 데이터 형식 변이 카탈로그",
        "",
        "| 부처 | 열 구조 | 비고 |",
        "|------|------|------|",
    ]
    for dept, info in variation_catalog.items():
        col_counts = "/".join(str(c) for c in sorted(info.get("column_counts", set())))
        markers = "신규마커" if info.get("new_markers") else "-"
        lines.append(f"| {dept} | {col_counts}열 | {markers} |")

    lines += [
        "",
        "---",
        "",
        "Q의 지침의 따라 Claude Code - claude-opus-4-6이 2026-03-09에 생성했습니다.",
    ]

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[리포트] {REPORT_MD}")


# ─── 출력 저장 ────────────────────────────────────────────────────────────────

DB_PATH = BASE_DIR / "data" / "budget.db"


def save_outputs(records: list, audits: list):
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(AUDIT_CSV, index=False, encoding="utf-8-sig")
    print(f"[저장] {OUT_CSV}")
    print(f"[저장] {AUDIT_CSV}")


def save_db(records: list):
    """
    SQLite DB 저장 및 대시보드용 뷰 생성.
    extract_all.py의 save_db를 계승, budget_data_verified 기반으로 저장.
    """
    import sqlite3

    df = pd.DataFrame(records)
    conn = sqlite3.connect(DB_PATH)

    df.to_sql("projects", conn, if_exists="replace", index=False)

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
    print(f"[저장] {DB_PATH}")


# ─── 진입점 ──────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="2026 AI 예산 PDF 재추출 및 검증")
    parser.add_argument(
        "--pilot", nargs="*",
        metavar="부처명",
        help="파일럿 부처 지정 (예: 감사원 교육부 경찰청). 미지정 시 전체 실행",
    )
    args = parser.parse_args()

    pilot = args.pilot  # None이면 전체

    print("=" * 60)
    if pilot:
        print(f"[파일럿] 대상 부처: {', '.join(pilot)}")
    else:
        print("[전체] 41개 부처 추출 시작")
    print("=" * 60)

    records, audits, catalog = run_extraction(pilot_depts=pilot)
    save_outputs(records, audits)
    save_db(records)
    generate_report(records, audits, catalog)

    # 간략 요약
    df = pd.DataFrame(records)
    extracted = df["budget_2026"].notna().sum()
    total = len(df)
    print("\n" + "=" * 60)
    print(f"추출 완료: {extracted}/{total} ({extracted/total*100:.1f}%)")
    if total > 0:
        total_2026 = df["budget_2026"].sum()
        print(f"2026 총 예산 합계: {total_2026:,.0f} 백만원 ({total_2026/1e6:.2f}조원)")
    print("=" * 60)


if __name__ == "__main__":
    main()
