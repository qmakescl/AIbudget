const fs = require('fs');
const data = JSON.parse(fs.readFileSync('data.json', 'utf8'));

const formatNum = (num) => new Intl.NumberFormat('ko-KR').format(num || 0);

try {
    const kpi = data.kpi;
    const meta = data.meta;
    console.log("total_budget_2026_bil:", kpi.total_budget_2026_bil);
    console.log("kpi-total-budget:", `${kpi.total_budget_2026_bil.toFixed(2)} 조원`);
    const netChange = meta.net_change_mil / 100;
    const arrow = netChange >= 0 ? '▲' : '▼';
    console.log("kpi-trend-budget:", `${arrow} 전년 대비 ${formatNum(Math.round(Math.abs(netChange)))}억 원 ${netChange >= 0 ? '증가' : '감소'}`);
    console.log("kpi-total-projects:", formatNum(kpi.total_projects) + '개');
    console.log("kpi-new-projects:", formatNum(kpi.new_projects) + '개');
    console.log("kpi-new-ratio:", ((kpi.new_projects / kpi.total_projects) * 100).toFixed(1));
    console.log("kpi-inc-count:", formatNum(kpi.increased_projects));
    console.log("kpi-dec-count:", formatNum(kpi.decreased_projects));
    console.log("frozen_projects:", kpi.frozen_projects);
    console.log("increased_total_mil:", formatNum(kpi.increased_total_mil));
    console.log("decreased_total_mil:", formatNum(kpi.decreased_total_mil));
    console.log("dept_summary count:", data.dept_summary.length);
    console.log("projects count:", data.projects.length);
} catch (e) {
    console.error(e);
}
