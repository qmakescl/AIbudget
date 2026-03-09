"""
prepare_data.py — budget_data_verified.csv → dashboard 데이터 변환

출력 파일:
  dashboard/data.json
  ├── meta          전체 통계 요약
  ├── kpi           KPI 카드용 수치
  ├── dept_summary  부처별 집계 (41개, 예산 내림차순)
  ├── projects      전체 사업 목록 (533건)
  ├── top10_increased  증가액 Top 10
  ├── top10_decreased  감소액 Top 10
  └── dept_projects 부처별 사업 목록 맵

  dashboard/dept_summary.csv   — 부처별 요약 (대시보드 테이블용)
  dashboard/projects.csv       — 전체 사업 정제본 (필터링/검색용)
"""

import json
import math
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent.parent
CSV_PATH = BASE_DIR / "data" / "budget_data_verified.csv"
DASH_DIR = Path(__file__).parent
OUT_JSON = DASH_DIR / "data.json"
OUT_DEPT_CSV = DASH_DIR / "dept_summary.csv"
OUT_PROJ_CSV = DASH_DIR / "projects.csv"


def nan_to_none(v):
    """pandas NaN/float nan → JSON null."""
    if v is None:
        return None
    try:
        if math.isnan(float(v)):
            return None
        return v
    except (TypeError, ValueError):
        return v


def load_df() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    # 실질 2025 예산: 추경 우선, 없으면 본예산
    df["budget_2025_actual"] = df["budget_2025_sup"].fillna(df["budget_2025"])
    return df


def build_meta(df: pd.DataFrame) -> dict:
    import datetime
    b2026 = df["budget_2026"].sum()
    b2025 = df["budget_2025_actual"].sum()
    return {
        "generated_at": datetime.date.today().isoformat(),
        "source_csv": "data/budget_data_verified.csv",
        "total_projects": int(len(df)),
        "total_depts": int(df["dept_name"].nunique()),
        "budget_2026_total_mil": round(b2026, 0),
        "budget_2025_total_mil": round(b2025, 0),
        "net_change_mil": round(b2026 - b2025, 0),
    }


def build_kpi(df: pd.DataFrame) -> dict:
    has_change = df[df["change_amount"].notna()]
    return {
        "total_budget_2026_bil": round(df["budget_2026"].sum() / 1e6, 4),  # 조원
        "total_projects": int(len(df)),
        "new_projects": int(df["is_new"].sum()),
        "increased_projects": int((has_change["change_amount"] > 0).sum()),
        "decreased_projects": int((has_change["change_amount"] < 0).sum()),
        "frozen_projects": int((has_change["change_amount"] == 0).sum()),
        "increased_total_mil": round(has_change[has_change["change_amount"] > 0]["change_amount"].sum(), 0),
        "decreased_total_mil": round(has_change[has_change["change_amount"] < 0]["change_amount"].sum(), 0),
    }


def build_dept_summary(df: pd.DataFrame) -> list:
    grp = df.groupby("dept_name")
    rows = []
    for dept, g in grp:
        b2025 = g["budget_2025_actual"].sum()
        b2026 = g["budget_2026"].sum()
        chg   = g["change_amount"].sum()
        rows.append({
            "dept_name": dept,
            "project_count": int(len(g)),
            "budget_2025_mil": round(b2025, 0),
            "budget_2026_mil": round(b2026, 0),
            "change_amount_mil": round(chg, 0),
            "change_rate_pct": round((b2026 - b2025) / b2025 * 100, 1) if b2025 else None,
            "new_count": int(g["is_new"].sum()),
            "increased_count": int((g["change_amount"].fillna(0) > 0).sum()),
            "decreased_count": int((g["change_amount"].fillna(0) < 0).sum()),
            "frozen_count": int((g["change_amount"].fillna(0) == 0).sum()),
        })
    # 2026 예산 내림차순
    rows.sort(key=lambda r: r["budget_2026_mil"], reverse=True)
    return rows


def build_projects(df: pd.DataFrame) -> list:
    records = []
    for _, row in df.iterrows():
        records.append({
            "dept_name": row["dept_name"],
            "project_no": int(row["project_no"]),
            "project_name": row["project_name"],
            "budget_2024": nan_to_none(row["budget_2024"]),
            "budget_2025": nan_to_none(row["budget_2025_actual"]),
            "budget_2026": nan_to_none(row["budget_2026"]),
            "change_amount": nan_to_none(row["change_amount"]),
            "change_rate": nan_to_none(row["change_rate"]),
            "is_new": bool(row["is_new"]),
            "description": None if pd.isna(row["description"]) else str(row["description"])[:300],
        })
    return records


def build_top10(df: pd.DataFrame) -> tuple[list, list]:
    has_b = df[df["budget_2026"].notna() & df["change_amount"].notna() & (~df["is_new"])]

    top_inc = (
        has_b[has_b["change_amount"] > 0]
        .nlargest(10, "change_amount")
        [["dept_name", "project_name", "budget_2025_actual", "budget_2026", "change_amount", "change_rate"]]
    )
    top_dec = (
        has_b[has_b["change_amount"] < 0]
        .nsmallest(10, "change_amount")
        [["dept_name", "project_name", "budget_2025_actual", "budget_2026", "change_amount", "change_rate"]]
    )

    def to_list(frame):
        result = []
        for _, r in frame.iterrows():
            result.append({
                "dept_name": r["dept_name"],
                "project_name": r["project_name"],
                "budget_2025_mil": nan_to_none(r["budget_2025_actual"]),
                "budget_2026_mil": nan_to_none(r["budget_2026"]),
                "change_amount_mil": nan_to_none(r["change_amount"]),
                "change_rate_pct": nan_to_none(r["change_rate"]),
            })
        return result

    return to_list(top_inc), to_list(top_dec)


def build_dept_projects(df: pd.DataFrame) -> dict:
    """부처명 → 사업 목록 맵 (드롭다운 선택 시 즉시 렌더링용)."""
    result = {}
    for dept, g in df.groupby("dept_name"):
        result[dept] = []
        for _, row in g.iterrows():
            result[dept].append({
                "project_name": row["project_name"],
                "budget_2024": nan_to_none(row["budget_2024"]),
                "budget_2025": nan_to_none(row["budget_2025_actual"]),
                "budget_2026": nan_to_none(row["budget_2026"]),
                "change_amount": nan_to_none(row["change_amount"]),
                "change_rate": nan_to_none(row["change_rate"]),
                "is_new": bool(row["is_new"]),
            })
    return result


def save_csvs(df: pd.DataFrame, dept_rows: list):
    """부처 요약 CSV 및 정제 사업 CSV 저장."""
    # 부처 요약 CSV
    dept_df = pd.DataFrame(dept_rows).rename(columns={
        "dept_name": "부처명",
        "project_count": "사업수",
        "budget_2025_mil": "2025예산_백만원",
        "budget_2026_mil": "2026예산_백만원",
        "change_amount_mil": "증감액_백만원",
        "change_rate_pct": "증감률_%",
        "new_count": "신규사업수",
        "increased_count": "증가사업수",
        "decreased_count": "감소사업수",
        "frozen_count": "동결사업수",
    })
    dept_df.to_csv(OUT_DEPT_CSV, index=False, encoding="utf-8-sig")

    # 전체 사업 정제 CSV (대시보드 테이블·필터링용)
    proj_df = df[[
        "dept_name", "project_no", "project_name",
        "budget_2024", "budget_2025_actual", "budget_2026",
        "change_amount", "change_rate", "is_new", "description",
    ]].rename(columns={
        "dept_name": "부처명",
        "project_no": "사업번호",
        "project_name": "사업명",
        "budget_2024": "2024결산_백만원",
        "budget_2025_actual": "2025예산_백만원",
        "budget_2026": "2026예산_백만원",
        "change_amount": "증감액_백만원",
        "change_rate": "증감률_%",
        "is_new": "신규여부",
        "description": "사업내용",
    })
    proj_df.to_csv(OUT_PROJ_CSV, index=False, encoding="utf-8-sig")


def main():
    print(f"[로드] {CSV_PATH}")
    df = load_df()
    print(f"  {len(df)}건, {df['dept_name'].nunique()}개 부처")

    dept_rows = build_dept_summary(df)
    top_inc, top_dec = build_top10(df)

    data = {
        "meta": build_meta(df),
        "kpi": build_kpi(df),
        "dept_summary": dept_rows,
        "projects": build_projects(df),
        "top10_increased": top_inc,
        "top10_decreased": top_dec,
        "dept_projects": build_dept_projects(df),
    }

    DASH_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    save_csvs(df, dept_rows)

    size_kb = OUT_JSON.stat().st_size / 1024
    print(f"[저장] {OUT_JSON} ({size_kb:.1f} KB)")
    print(f"[저장] {OUT_DEPT_CSV}")
    print(f"[저장] {OUT_PROJ_CSV}")
    print()
    print("=== KPI ===")
    kpi = data["kpi"]
    print(f"  2026 총예산: {kpi['total_budget_2026_bil']:.2f}조원")
    print(f"  전체 사업수: {kpi['total_projects']}건")
    print(f"  신규사업:    {kpi['new_projects']}건")
    print(f"  예산 증가:   {kpi['increased_projects']}건  (+{kpi['increased_total_mil']:,.0f}백만원)")
    print(f"  예산 감소:   {kpi['decreased_projects']}건  ({kpi['decreased_total_mil']:,.0f}백만원)")
    print(f"  예산 동결:   {kpi['frozen_projects']}건")


if __name__ == "__main__":
    main()
