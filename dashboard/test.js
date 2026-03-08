const fs = require('fs');
const data = JSON.parse(fs.readFileSync('data.json', 'utf8'));

const formatNum = (num) => new Intl.NumberFormat('ko-KR').format(num || 0);

try {
    const summary = data.summary;
    console.log("total_budget_2026:", summary.total_budget_2026);
    console.log("kpi-total-budget:", `${(summary.total_budget_2026 / 10000).toFixed(1)} 조원`);
    console.log("kpi-trend-budget:", `▲ 전년 대비 ${formatNum(summary.increase_amount)}억 원 증가`);
    console.log("kpi-total-projects:", formatNum(summary.total_projects) + '개');
    console.log("kpi-new-projects:", formatNum(summary.new_projects) + '개');
    console.log("kpi-new-ratio:", ((summary.new_projects / summary.total_projects) * 100).toFixed(1));
    console.log("kpi-inc-count:", formatNum(summary.increase_projects));
    console.log("kpi-dec-count:", formatNum(summary.decrease_projects));
} catch (e) {
    console.error(e);
}
