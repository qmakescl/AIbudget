import pandas as pd
import json
import os

def prepare_dashboard_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, '../data/budget_data.csv')
    out_path = os.path.join(base_dir, 'data.json')
    
    df = pd.read_csv(data_path)
    
    # NaN to None for JSON serialization (must cast to object to hold None)
    df = df.astype(object).where(pd.notnull(df), None)
    
    # 1. Summary
    total_budget_2026 = df['budget_2026'].sum()
    total_budget_2025 = df['budget_2025'].sum()
    total_projects = len(df)
    new_projects = int(df['is_new'].sum())
    net_change = total_budget_2026 - total_budget_2025  # 순증감
    
    # 2. Dept Summary
    dept_stats = df.groupby('dept_name').agg(
        project_count=('project_name', 'count'),
        budget_2026=('budget_2026', 'sum'),
        new_count=('is_new', 'sum'),
        increase_count=('change_amount', lambda x: (x > 0).sum()),
        decrease_count=('change_amount', lambda x: (x < 0).sum()),
        freeze_count=('change_amount', lambda x: (x == 0).sum())
    ).reset_index()
    
    # Sort by budget_2026 desc
    dept_stats = dept_stats.sort_values('budget_2026', ascending=False)
    
    # 3. Project records for table
    # Simplify records for the frontend
    records = df.to_dict('records')
    
    data = {
        "summary": {
            "total_budget_2026": float(total_budget_2026),
            "total_projects": total_projects,
            "new_projects": new_projects,
            "increase_projects": int((df['change_amount'] > 0).sum()),
            "decrease_projects": int((df['change_amount'] < 0).sum()),
            "increase_amount": float(df[df['change_amount'] > 0]['change_amount'].sum()),
            "decrease_amount": float(df[df['change_amount'] < 0]['change_amount'].sum()),
            "net_change": float(net_change),
            "total_budget_2025": float(total_budget_2025),
        },
        "dept_stats": dept_stats.to_dict('records'),
        "projects": records
    }
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"✅ Dashboard data generated at {out_path}")

if __name__ == "__main__":
    prepare_dashboard_data()
