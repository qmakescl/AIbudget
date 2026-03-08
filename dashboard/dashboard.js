// Define Color Palette
const colors = {
    blue: '#3b82f6',
    blueLight: 'rgba(59, 130, 246, 0.5)',
    red: '#ef4444',
    redLight: 'rgba(239, 68, 68, 0.5)',
    green: '#10b981',
    greenLight: 'rgba(16, 185, 129, 0.5)',
    purple: '#8b5cf6',
    purpleLight: 'rgba(139, 92, 246, 0.5)',
    gray: '#64748b',
    grayLight: 'rgba(100, 116, 139, 0.5)',
    textPrimary: '#f8fafc',
    textSecondary: '#94a3b8',
    bgPanel: 'rgba(30, 41, 59, 0.7)',
    gridLines: 'rgba(255, 255, 255, 0.1)'
};

Chart.defaults.color = colors.textSecondary;
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(15, 23, 42, 0.9)';
Chart.defaults.plugins.tooltip.titleColor = colors.textPrimary;
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.cornerRadius = 8;
Chart.defaults.plugins.tooltip.borderColor = colors.gridLines;
Chart.defaults.plugins.tooltip.borderWidth = 1;

let globalData = null;
let charts = {};
let tabRendered = { all: false, new: false, increase: false, decrease: false };

const formatNum = (num) => new Intl.NumberFormat('ko-KR').format(num || 0);
const toUnit = (val) => val != null ? Math.round(val / 100) : 0;
const UNIT_LABEL = '억원';

// ======== Theme Toggle ========
function initTheme() {
    const saved = localStorage.getItem('dashboard-theme');
    if (saved === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        updateThemeIcon('light');
        applyChartTheme('light');
    }
    document.getElementById('themeToggle').addEventListener('click', toggleTheme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    if (next === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
    localStorage.setItem('dashboard-theme', next);
    updateThemeIcon(next);
    applyChartTheme(next);
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('themeIcon');
    icon.className = theme === 'light' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
}

function applyChartTheme(theme) {
    const textColor = theme === 'light' ? '#475569' : '#94a3b8';
    const gridColor = theme === 'light' ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.1)';
    const tooltipBg = theme === 'light' ? 'rgba(255,255,255,0.95)' : 'rgba(15,23,42,0.9)';
    const tooltipTitle = theme === 'light' ? '#1e293b' : '#f8fafc';

    Chart.defaults.color = textColor;
    Chart.defaults.plugins.tooltip.backgroundColor = tooltipBg;
    Chart.defaults.plugins.tooltip.titleColor = tooltipTitle;
    Chart.defaults.plugins.tooltip.bodyColor = textColor;

    // Update existing chart instances
    Object.values(charts).forEach(chart => {
        if (!chart || !chart.options) return;
        if (chart.options.scales) {
            Object.values(chart.options.scales).forEach(scale => {
                if (scale.grid) scale.grid.color = gridColor;
                if (scale.title) scale.title.color = textColor;
                if (scale.ticks) scale.ticks.color = textColor;
            });
        }
        chart.update('none');
    });
}

// ======== Init ========
async function initDashboard() {
    try {
        const response = await fetch("data.json");
        const data = await response.json();
        globalData = data;

        initTheme();
        renderKPIs(data.summary);
        setupTabs();
        // Render default tab
        renderAllTab(data);
        tabRendered.all = true;

    } catch (error) {
        console.error('Error loading data:', error);
        document.getElementById('kpi-total-budget').innerText = 'Data Load Error';
        document.getElementById('kpi-trend-budget').innerText = 'Data Load Error';
    }
}

// ======== KPIs ========
function renderKPIs(summary) {
    document.getElementById('kpi-total-budget').innerText = `${(summary.total_budget_2026 / 1000000).toFixed(1)} 조원`;
    const netChange = summary.net_change / 100;
    const arrow = netChange >= 0 ? '▲' : '▼';
    const trendClass = netChange >= 0 ? 'trend-up' : 'trend-down';
    document.getElementById('kpi-trend-budget').className = `kpi-trend ${trendClass}`;
    document.getElementById('kpi-trend-budget').innerHTML = `${arrow} 전년 대비 ${formatNum(Math.round(Math.abs(netChange)))}억 원 ${netChange >= 0 ? '증가' : '감소'}`;
    document.getElementById('kpi-total-projects').innerText = formatNum(summary.total_projects) + '개';
    document.getElementById('kpi-new-projects').innerText = formatNum(summary.new_projects) + '개';
    document.getElementById('kpi-new-ratio').innerText = ((summary.new_projects / summary.total_projects) * 100).toFixed(1);
    document.getElementById('kpi-inc-count').innerText = formatNum(summary.increase_projects);
    document.getElementById('kpi-dec-count').innerText = formatNum(summary.decrease_projects);
}

// ======== Tab Navigation ========
function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const tabId = btn.dataset.tab;
            document.getElementById('tab-' + tabId).classList.add('active');

            // Lazy render
            if (!tabRendered[tabId]) {
                if (tabId === 'new') renderNewTab(globalData);
                if (tabId === 'increase') renderChangeTab(globalData, 'increase');
                if (tabId === 'decrease') renderChangeTab(globalData, 'decrease');
                tabRendered[tabId] = true;
            }
        });
    });
}

// ======== TAB: 전체사업 ========
function renderAllTab(data) {
    // 1. Dept Budget Bar
    const ctxDept = document.getElementById('deptBudgetChart').getContext('2d');
    const depts = data.dept_stats.slice(0, 15);
    charts.dept = new Chart(ctxDept, {
        type: 'bar',
        data: {
            labels: depts.map(d => d.dept_name),
            datasets: [{
                label: `2026 예산 (${UNIT_LABEL})`,
                data: depts.map(d => toUnit(d.budget_2026)),
                backgroundColor: colors.blueLight, borderColor: colors.blue, borderWidth: 1, borderRadius: 4
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                y: { grid: { color: colors.gridLines }, title: { display: true, text: `단위: ${UNIT_LABEL}`, color: colors.textSecondary } },
                x: { grid: { display: false } }
            },
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => [`예산: ${formatNum(ctx.raw)} ${UNIT_LABEL}`, `사업 수: ${depts[ctx.dataIndex].project_count}건`] } }
            }
        }
    });

    // 2. Budget Change Doughnut
    const ctxChange = document.getElementById('budgetChangeChart').getContext('2d');
    charts.change = new Chart(ctxChange, {
        type: 'doughnut',
        data: {
            labels: ['증가', '감소', '동결', '신규사업'],
            datasets: [{
                data: [
                    data.summary.increase_projects - data.summary.new_projects,
                    data.summary.decrease_projects,
                    data.summary.total_projects - data.summary.increase_projects - data.summary.decrease_projects - data.summary.new_projects,
                    data.summary.new_projects
                ],
                backgroundColor: [colors.blueLight, colors.redLight, colors.grayLight, colors.greenLight],
                borderColor: [colors.blue, colors.red, colors.gray, colors.green], borderWidth: 1
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'right' } } }
    });

    // 3. New Projects Doughnut
    const ctxNew = document.getElementById('newProjectChart').getContext('2d');
    const newDepts = data.dept_stats.filter(d => d.new_count > 0).sort((a, b) => b.new_count - a.new_count).slice(0, 5);
    const otherNewCount = data.summary.new_projects - newDepts.reduce((sum, d) => sum + d.new_count, 0);
    charts.newDonut = new Chart(ctxNew, {
        type: 'doughnut',
        data: {
            labels: [...newDepts.map(d => d.dept_name), '기타'],
            datasets: [{
                data: [...newDepts.map(d => d.new_count), otherNewCount],
                backgroundColor: [colors.purpleLight, colors.blueLight, colors.greenLight, '#fcd34d88', '#f8717188', colors.grayLight],
                borderColor: [colors.purple, colors.blue, colors.green, '#f59e0b', '#dc2626', colors.gray], borderWidth: 1
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'right' } } }
    });

    // 4. Drilldown
    setupDrilldown(data);
}

function setupDrilldown(data) {
    const select = document.getElementById('deptSelect');
    [...data.dept_stats].sort((a, b) => a.dept_name.localeCompare(b.dept_name)).forEach(d => {
        let opt = document.createElement('option');
        opt.value = d.dept_name;
        opt.textContent = `${d.dept_name} (${d.project_count}건)`;
        select.appendChild(opt);
    });
    select.addEventListener('change', () => updateDrilldown(select.value));
    document.getElementById('searchInput').addEventListener('input', () => updateTable(select.value, document.getElementById('searchInput').value));
    updateDrilldown('all');
}

function updateDrilldown(deptName) {
    updateTable(deptName, document.getElementById('searchInput').value);
    updateTrendChart(deptName);
}

function updateTable(deptName, searchTerm) {
    let projs = globalData.projects;
    if (deptName !== 'all') projs = projs.filter(p => p.dept_name === deptName);
    if (searchTerm) { const t = searchTerm.toLowerCase(); projs = projs.filter(p => p.project_name.toLowerCase().includes(t)); }
    projs.sort((a, b) => (b.budget_2026 || 0) - (a.budget_2026 || 0));

    const tbody = document.getElementById('projectsTableBody');
    tbody.innerHTML = '';
    projs.forEach(p => {
        const tr = document.createElement('tr');
        let badge = '';
        if (p.is_new) badge = '<span class="badge badge-new">신규사업</span>';
        else if (p.change_amount > 0) { const r = p.change_rate != null ? ` (+${p.change_rate.toFixed(1)}%)` : ''; badge = `<span class="badge badge-inc">▲ ${formatNum(toUnit(p.change_amount))}${r}</span>`; }
        else if (p.change_amount < 0) { const r = p.change_rate != null ? ` (${p.change_rate.toFixed(1)}%)` : ''; badge = `<span class="badge badge-dec">▼ ${formatNum(toUnit(Math.abs(p.change_amount)))}${r}</span>`; }
        else badge = '<span class="badge badge-eq">- 0</span>';

        const tooltip = p.description ? `<div class="project-tooltip">${p.description}</div>` : '';
        tr.innerHTML = `<td>${p.dept_name}</td>
            <td class="project-name-cell" style="font-weight:500">${p.project_name}${tooltip}</td>
            <td class="text-right">${formatNum(toUnit(p.budget_2024))}</td><td class="text-right">${formatNum(toUnit(p.budget_2025))}</td>
            <td class="text-right" style="color:var(--blue);font-weight:600">${formatNum(toUnit(p.budget_2026))}</td>
            <td class="text-right">${badge}</td><td class="text-center">${p.is_new ? '신규' : '계속'}</td>`;
        tbody.appendChild(tr);
    });
}

function updateTrendChart(deptName) {
    let projs = globalData.projects;
    if (deptName !== 'all') projs = projs.filter(p => p.dept_name === deptName);
    projs = projs.sort((a, b) => (b.budget_2026 || 0) - (a.budget_2026 || 0)).slice(0, 10);

    if (charts.trend) charts.trend.destroy();
    charts.trend = new Chart(document.getElementById('yearlyTrendChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: projs.map(p => p.project_name.length > 20 ? p.project_name.substring(0, 20) + '...' : p.project_name),
            datasets: [
                { label: '2024', data: projs.map(p => toUnit(p.budget_2024)), backgroundColor: colors.grayLight, borderColor: colors.gray, borderWidth: 1 },
                { label: '2025', data: projs.map(p => toUnit(p.budget_2025)), backgroundColor: colors.purpleLight, borderColor: colors.purple, borderWidth: 1 },
                { label: '2026', data: projs.map(p => toUnit(p.budget_2026)), backgroundColor: colors.blueLight, borderColor: colors.blue, borderWidth: 1 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: { y: { grid: { color: colors.gridLines }, title: { display: true, text: `단위: ${UNIT_LABEL}`, color: colors.textSecondary } }, x: { grid: { display: false } } },
            plugins: { tooltip: { callbacks: { title: items => projs[items[0].dataIndex].project_name, label: ctx => `${ctx.dataset.label}: ${formatNum(ctx.raw)} ${UNIT_LABEL}` } } }
        }
    });
}

// ======== TAB: 신규사업 ========
function renderNewTab(data) {
    const newProjs = data.projects.filter(p => p.is_new);
    const newBudgetTotal = newProjs.reduce((s, p) => s + (p.budget_2026 || 0), 0);

    document.getElementById('new-total-count').innerText = `총 ${newProjs.length}건`;
    document.getElementById('new-total-budget').innerText = `총 예산 ${formatNum(toUnit(newBudgetTotal))} ${UNIT_LABEL}`;

    // Aggregate by dept
    const deptBudgets = {}, deptCounts = {};
    newProjs.forEach(p => {
        deptBudgets[p.dept_name] = (deptBudgets[p.dept_name] || 0) + (p.budget_2026 || 0);
        deptCounts[p.dept_name] = (deptCounts[p.dept_name] || 0) + 1;
    });

    // 1. Bar chart
    const sorted = Object.entries(deptBudgets).sort((a, b) => b[1] - a[1]).slice(0, 15);
    charts.newBudget = new Chart(document.getElementById('newBudgetByDeptChart').getContext('2d'), {
        type: 'bar',
        data: { labels: sorted.map(d => d[0]), datasets: [{ label: `신규 예산 (${UNIT_LABEL})`, data: sorted.map(d => toUnit(d[1])), backgroundColor: colors.greenLight, borderColor: colors.green, borderWidth: 1, borderRadius: 4 }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: { y: { grid: { color: colors.gridLines }, title: { display: true, text: `단위: ${UNIT_LABEL}`, color: colors.textSecondary } }, x: { grid: { display: false } } },
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => [`예산: ${formatNum(ctx.raw)} ${UNIT_LABEL}`, `신규사업: ${deptCounts[sorted[ctx.dataIndex][0]]}건`] } } }
        }
    });

    // 2. Dept summary table
    renderDeptSummaryTable(deptCounts, data.projects, 'newDeptSummaryBody', 'var(--green)');

    // 3. Top 10 bar
    const top10 = [...newProjs].sort((a, b) => (b.budget_2026 || 0) - (a.budget_2026 || 0)).slice(0, 10);
    renderHorizontalBar('newTopProjectsChart', top10, p => toUnit(p.budget_2026), `2026 예산 (${UNIT_LABEL})`, colors.greenLight, colors.green, (ctx, i) => [`예산: ${formatNum(ctx.raw)} ${UNIT_LABEL}`, `부처: ${top10[i].dept_name}`]);

    // 4. Table with dept select
    setupCategoryTable(newProjs, deptCounts, 'newDeptSelect', 'newSearchInput', 'newProjectsTableBody', 'new');
}

// ======== TAB: 증가/감소 (공통) ========
function renderChangeTab(data, type) {
    const isInc = type === 'increase';
    const filteredProjs = data.projects.filter(p => !p.is_new && (isInc ? p.change_amount > 0 : p.change_amount < 0));
    const totalChange = filteredProjs.reduce((s, p) => s + Math.abs(p.change_amount || 0), 0);
    const prefix = isInc ? 'inc' : 'dec';
    const themeColor = isInc ? colors.blue : colors.red;
    const themeColorLight = isInc ? colors.blueLight : colors.redLight;
    const cssVar = isInc ? 'var(--blue)' : 'var(--red)';
    const label = isInc ? '증가' : '감소';

    document.getElementById(`${prefix}-total-count`).innerText = `총 ${filteredProjs.length}건`;
    document.getElementById(`${prefix}-total-budget`).innerText = `${label}액 합계 ${formatNum(toUnit(totalChange))} ${UNIT_LABEL}`;

    // Aggregate by dept
    const deptAmounts = {}, deptCounts = {};
    filteredProjs.forEach(p => {
        deptAmounts[p.dept_name] = (deptAmounts[p.dept_name] || 0) + Math.abs(p.change_amount || 0);
        deptCounts[p.dept_name] = (deptCounts[p.dept_name] || 0) + 1;
    });

    // 1. Bar chart
    const sorted = Object.entries(deptAmounts).sort((a, b) => b[1] - a[1]).slice(0, 15);
    charts[`${prefix}Budget`] = new Chart(document.getElementById(`${prefix}BudgetByDeptChart`).getContext('2d'), {
        type: 'bar',
        data: { labels: sorted.map(d => d[0]), datasets: [{ label: `${label}액 (${UNIT_LABEL})`, data: sorted.map(d => toUnit(d[1])), backgroundColor: themeColorLight, borderColor: themeColor, borderWidth: 1, borderRadius: 4 }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: { y: { grid: { color: colors.gridLines }, title: { display: true, text: `단위: ${UNIT_LABEL}`, color: colors.textSecondary } }, x: { grid: { display: false } } },
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => [`${label}액: ${formatNum(ctx.raw)} ${UNIT_LABEL}`, `사업 수: ${deptCounts[sorted[ctx.dataIndex][0]]}건`] } } }
        }
    });

    // 2. Dept summary table
    renderDeptSummaryTable(deptCounts, data.projects, `${prefix}DeptSummaryBody`, cssVar);

    // 3. Top 10 bar
    const top10 = [...filteredProjs].sort((a, b) => Math.abs(b.change_amount) - Math.abs(a.change_amount)).slice(0, 10);
    renderHorizontalBar(`${prefix}TopProjectsChart`, top10, p => toUnit(Math.abs(p.change_amount)), `${label}액 (${UNIT_LABEL})`, themeColorLight, themeColor, (ctx, i) => [`${label}액: ${formatNum(ctx.raw)} ${UNIT_LABEL}`, `부처: ${top10[i].dept_name}`, `${label}율: ${top10[i].change_rate != null ? top10[i].change_rate.toFixed(1) + '%' : '-'}`]);

    // 4. Table with dept select
    setupCategoryTable(filteredProjs, deptCounts, `${prefix}DeptSelect`, `${prefix}SearchInput`, `${prefix}ProjectsTableBody`, type);
}

// ======== Shared Helpers ========

function renderDeptSummaryTable(catDeptCounts, allProjects, tbodyId, accentColor) {
    const totalByDept = {};
    allProjects.forEach(p => { totalByDept[p.dept_name] = (totalByDept[p.dept_name] || 0) + 1; });

    const rows = Object.entries(catDeptCounts)
        .map(([dept, cnt]) => ({ dept, cnt, total: totalByDept[dept] || 0, ratio: ((cnt / (totalByDept[dept] || 1)) * 100).toFixed(1) }))
        .sort((a, b) => b.cnt - a.cnt);

    const tbody = document.getElementById(tbodyId);
    tbody.innerHTML = '';
    rows.forEach(d => {
        const tr = document.createElement('tr');
        const ratioColor = parseFloat(d.ratio) >= 50 ? accentColor : 'var(--text-secondary)';
        tr.innerHTML = `<td>${d.dept}</td><td class="text-right" style="color:${accentColor};font-weight:600">${d.cnt}</td><td class="text-right">${d.total}</td><td class="text-right" style="color:${ratioColor};font-weight:500">${d.ratio}%</td>`;
        tbody.appendChild(tr);
    });
}

function renderHorizontalBar(canvasId, items, valueFn, label, bgColor, borderColor, tooltipFn) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    const chartKey = canvasId;
    if (charts[chartKey]) charts[chartKey].destroy();
    charts[chartKey] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: items.map(p => p.project_name.length > 15 ? p.project_name.substring(0, 15) + '...' : p.project_name),
            datasets: [{ label, data: items.map(valueFn), backgroundColor: bgColor, borderColor, borderWidth: 1, borderRadius: 4 }]
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            scales: { x: { grid: { color: colors.gridLines }, title: { display: true, text: `단위: ${UNIT_LABEL}`, color: colors.textSecondary } }, y: { grid: { display: false } } },
            plugins: { legend: { display: false }, tooltip: { callbacks: { title: its => items[its[0].dataIndex].project_name, label: ctx => tooltipFn(ctx, ctx.dataIndex) } } }
        }
    });
}

function setupCategoryTable(projs, deptCounts, selectId, searchId, tbodyId, type) {
    const select = document.getElementById(selectId);
    Object.keys(deptCounts).sort((a, b) => a.localeCompare(b)).forEach(d => {
        let opt = document.createElement('option');
        opt.value = d;
        opt.textContent = `${d} (${deptCounts[d]}건)`;
        select.appendChild(opt);
    });

    const update = () => renderCategoryTable(projs, select.value, document.getElementById(searchId).value, tbodyId, type);
    select.addEventListener('change', update);
    document.getElementById(searchId).addEventListener('input', update);
    update();
}

function renderCategoryTable(allProjs, deptFilter, searchTerm, tbodyId, type) {
    let projs = allProjs;
    if (deptFilter && deptFilter !== 'all') projs = projs.filter(p => p.dept_name === deptFilter);
    if (searchTerm) { const t = searchTerm.toLowerCase(); projs = projs.filter(p => p.project_name.toLowerCase().includes(t) || p.dept_name.toLowerCase().includes(t)); }

    if (type === 'new') {
        projs = [...projs].sort((a, b) => (b.budget_2026 || 0) - (a.budget_2026 || 0));
    } else {
        projs = [...projs].sort((a, b) => Math.abs(b.change_amount || 0) - Math.abs(a.change_amount || 0));
    }

    const tbody = document.getElementById(tbodyId);
    tbody.innerHTML = '';

    projs.forEach(p => {
        const tr = document.createElement('tr');
        const tooltip = p.description ? `<div class="project-tooltip">${p.description}</div>` : '';
        if (type === 'new') {
            tr.innerHTML = `<td>${p.dept_name}</td>
                <td class="project-name-cell" style="font-weight:500">${p.project_name}${tooltip}</td>
                <td class="text-right" style="color:var(--green);font-weight:600">${formatNum(toUnit(p.budget_2026))}</td>`;
        } else {
            const isInc = type === 'increase';
            const cssColor = isInc ? 'var(--blue)' : 'var(--red)';
            const arrow = isInc ? '▲' : '▼';
            const rateStr = p.change_rate != null ? `${p.change_rate > 0 ? '+' : ''}${p.change_rate.toFixed(1)}%` : '-';
            tr.innerHTML = `<td>${p.dept_name}</td>
                <td class="project-name-cell" style="font-weight:500">${p.project_name}${tooltip}</td>
                <td class="text-right">${formatNum(toUnit(p.budget_2025))}</td>
                <td class="text-right">${formatNum(toUnit(p.budget_2026))}</td>
                <td class="text-right" style="color:${cssColor};font-weight:600">${arrow} ${formatNum(toUnit(Math.abs(p.change_amount)))}</td>
                <td class="text-right" style="color:${cssColor}">${rateStr}</td>`;
        }
        tbody.appendChild(tr);
    });
}

// Start
document.addEventListener('DOMContentLoaded', initDashboard);
