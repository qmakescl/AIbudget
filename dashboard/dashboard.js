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
let tabRendered = { all: false, new: false, increase: false, decrease: false, dept: false };

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
        initTooltipTracking();
        renderKPIs(data.kpi, data.meta);
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
function renderKPIs(kpi, meta) {
    document.getElementById('kpi-total-budget').innerText = `${kpi.total_budget_2026_bil.toFixed(2)} 조원`;
    const netChange = meta.net_change_mil / 100;  // 백만원 → 억원
    const arrow = netChange >= 0 ? '▲' : '▼';
    const trendClass = netChange >= 0 ? 'trend-up' : 'trend-down';
    document.getElementById('kpi-trend-budget').className = `kpi-trend ${trendClass}`;
    document.getElementById('kpi-trend-budget').innerHTML = `${arrow} 전년 대비 ${formatNum(Math.round(Math.abs(netChange)))}억 원 ${netChange >= 0 ? '증가' : '감소'}`;
    document.getElementById('kpi-total-projects').innerText = formatNum(kpi.total_projects) + '개';
    document.getElementById('kpi-new-projects').innerText = formatNum(kpi.new_projects) + '개';
    document.getElementById('kpi-new-ratio').innerText = ((kpi.new_projects / kpi.total_projects) * 100).toFixed(1);
    document.getElementById('kpi-inc-count').innerText = formatNum(kpi.increased_projects);
    document.getElementById('kpi-dec-count').innerText = formatNum(kpi.decreased_projects);
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
                if (tabId === 'dept') renderDeptTab(globalData);
                tabRendered[tabId] = true;
            }
        });
    });
}

// ======== TAB: 전체사업 ========
function renderAllTab(data) {
    // 1. Dept Budget Bar
    const ctxDept = document.getElementById('deptBudgetChart').getContext('2d');
    const depts = data.dept_summary.slice(0, 15);
    charts.dept = new Chart(ctxDept, {
        type: 'bar',
        data: {
            labels: depts.map(d => d.dept_name),
            datasets: [{
                label: `2026 예산 (${UNIT_LABEL})`,
                data: depts.map(d => toUnit(d.budget_2026_mil)),
                backgroundColor: colors.blueLight, borderColor: colors.blue, borderWidth: 1, borderRadius: 4
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                y: { grid: { color: colors.gridLines }, title: { display: true, text: `단위: ${UNIT_LABEL}`, color: colors.textSecondary } },
                x: {
                    grid: { display: false },
                    ticks: { maxRotation: 45, minRotation: 30, autoSkip: false, font: { size: 11 } }
                }
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
                    data.kpi.increased_projects - data.kpi.new_projects,
                    data.kpi.decreased_projects,
                    data.kpi.frozen_projects,
                    data.kpi.new_projects
                ],
                backgroundColor: [colors.blueLight, colors.redLight, colors.grayLight, colors.greenLight],
                borderColor: [colors.blue, colors.red, colors.gray, colors.green], borderWidth: 1
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, padding: 10 } } } }
    });

    // 3. New Projects Doughnut
    const ctxNew = document.getElementById('newProjectChart').getContext('2d');
    const newDepts = data.dept_summary.filter(d => d.new_count > 0).sort((a, b) => b.new_count - a.new_count).slice(0, 5);
    const otherNewCount = data.kpi.new_projects - newDepts.reduce((sum, d) => sum + d.new_count, 0);
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
        options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, padding: 10 } } } }
    });

    // 4. Scatter Chart: dept project count vs budget
    const deptIncDec = {};
    data.projects.forEach(p => {
        if (!deptIncDec[p.dept_name]) deptIncDec[p.dept_name] = { inc: 0, dec: 0 };
        if (!p.is_new && p.change_amount > 0) deptIncDec[p.dept_name].inc += p.change_amount;
        if (!p.is_new && p.change_amount < 0) deptIncDec[p.dept_name].dec += Math.abs(p.change_amount);
    });
    const scatterPoints = data.dept_summary.map(d => ({
        x: d.project_count,
        y: toUnit(d.budget_2026_mil),
        deptName: d.dept_name,
        newCount: d.new_count,
        incAmt: toUnit((deptIncDec[d.dept_name] || {}).inc || 0),
        decAmt: toUnit((deptIncDec[d.dept_name] || {}).dec || 0)
    }));
    const avgX = scatterPoints.reduce((s, d) => s + d.x, 0) / scatterPoints.length;
    const avgY = scatterPoints.reduce((s, d) => s + d.y, 0) / scatterPoints.length;

    function median(arr) {
        const s = [...arr].sort((a, b) => a - b);
        const m = Math.floor(s.length / 2);
        return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
    }
    const medX = median(scatterPoints.map(d => d.x));
    const medY = median(scatterPoints.map(d => d.y));

    // 피어슨 상관계수
    const n = scatterPoints.length;
    const sumXY = scatterPoints.reduce((s, d) => s + (d.x - avgX) * (d.y - avgY), 0);
    const sumX2 = scatterPoints.reduce((s, d) => s + (d.x - avgX) ** 2, 0);
    const sumY2 = scatterPoints.reduce((s, d) => s + (d.y - avgY) ** 2, 0);
    const corrR = (sumX2 && sumY2) ? sumXY / Math.sqrt(sumX2 * sumY2) : 0;

    // 타이틀 상관계수 채우기
    const corrEl = document.getElementById('scatterCorrLabel');
    if (corrEl) corrEl.textContent = `피어슨 상관계수 r = ${corrR.toFixed(3)}`;

    const avgLinesPlugin = {
        id: 'avgLines',
        afterDraw(chart) {
            const { ctx, scales: { x: xs, y: ys } } = chart;
            ctx.save();
            ctx.font = '11px Inter, sans-serif';

            // 평균선 (붉은 계열)
            ctx.setLineDash([5, 4]);
            ctx.strokeStyle = 'rgba(239,68,68,0.55)';
            ctx.lineWidth = 1.5;
            const axPx = xs.getPixelForValue(avgX);
            ctx.beginPath(); ctx.moveTo(axPx, ys.top); ctx.lineTo(axPx, ys.bottom); ctx.stroke();
            const ayPx = ys.getPixelForValue(avgY);
            ctx.beginPath(); ctx.moveTo(xs.left, ayPx); ctx.lineTo(xs.right, ayPx); ctx.stroke();
            ctx.fillStyle = 'rgba(239,68,68,0.75)';
            ctx.fillText(`평균 ${Math.round(avgX)}건`, axPx + 4, ys.top + 14);
            ctx.fillText(`평균 ${formatNum(Math.round(avgY))}억`, xs.left + 4, ayPx - 4);

            // 중앙값선 (노란 계열)
            ctx.strokeStyle = 'rgba(234,179,8,0.55)';
            const mxPx = xs.getPixelForValue(medX);
            ctx.beginPath(); ctx.moveTo(mxPx, ys.top); ctx.lineTo(mxPx, ys.bottom); ctx.stroke();
            const myPx = ys.getPixelForValue(medY);
            ctx.beginPath(); ctx.moveTo(xs.left, myPx); ctx.lineTo(xs.right, myPx); ctx.stroke();
            ctx.fillStyle = 'rgba(234,179,8,0.85)';
            ctx.fillText(`중앙값 ${Math.round(medX)}건`, mxPx + 4, ys.top + 28);
            ctx.fillText(`중앙값 ${formatNum(Math.round(medY))}억`, xs.left + 4, myPx - 4);

            ctx.setLineDash([]);

            // 우하단 범례
            const legendItems = [
                { color: 'rgba(239,68,68,0.8)',  label: `평균  (사업수 ${Math.round(avgX)}건 / 예산 ${formatNum(Math.round(avgY))}억)` },
                { color: 'rgba(234,179,8,0.9)',  label: `중앙값 (사업수 ${Math.round(medX)}건 / 예산 ${formatNum(Math.round(medY))}억)` },
            ];
            const lineLen = 22, gap = 6, rowH = 20, padX = 10, padY = 8;
            ctx.font = '11px Inter, sans-serif';
            const maxTw = Math.max(...legendItems.map(it => ctx.measureText(it.label).width));
            const boxW = lineLen + gap + maxTw + padX * 2;
            const boxH = legendItems.length * rowH + padY * 2 - (rowH - 14);
            const bx = xs.right - boxW - 8;
            const by = ys.bottom - boxH - 8;
            ctx.fillStyle = 'rgba(15,23,42,0.55)';
            ctx.beginPath();
            ctx.roundRect(bx, by, boxW, boxH, 6);
            ctx.fill();
            legendItems.forEach((item, i) => {
                const lx = bx + padX;
                const ly = by + padY + i * rowH + 11;
                ctx.strokeStyle = item.color;
                ctx.lineWidth = 2;
                ctx.setLineDash([5, 4]);
                ctx.beginPath(); ctx.moveTo(lx, ly - 3); ctx.lineTo(lx + lineLen, ly - 3); ctx.stroke();
                ctx.setLineDash([]);
                ctx.fillStyle = '#f8fafc';
                ctx.fillText(item.label, lx + lineLen + gap, ly);
            });

            ctx.restore();
        }
    };

    // Generate 1-2-5 sequence ticks for logarithmic axes
    function logTicks(scale) {
        const min = scale.min, max = scale.max;
        const e0 = Math.floor(Math.log10(Math.max(min, 0.1)));
        const e1 = Math.ceil(Math.log10(Math.max(max, 1)));
        const ticks = [];
        for (let e = e0; e <= e1; e++) {
            [1, 2, 5].forEach(m => {
                const v = m * Math.pow(10, e);
                if (v >= min * 0.5 && v <= max * 2) ticks.push({ value: v });
            });
        }
        scale.ticks = ticks;
    }

    charts.scatter = new Chart(document.getElementById('deptScatterChart').getContext('2d'), {
        type: 'scatter',
        data: {
            datasets: [{
                label: '부처',
                data: scatterPoints,
                backgroundColor: colors.purpleLight,
                borderColor: colors.purple,
                borderWidth: 1.5,
                pointRadius: 7,
                pointHoverRadius: 10
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'logarithmic',
                    grid: { color: colors.gridLines },
                    title: { display: true, text: '사업 수 (건)', color: colors.textSecondary },
                    afterBuildTicks: logTicks,
                    ticks: { callback: v => Number.isInteger(v) ? v + '건' : '' }
                },
                y: {
                    type: 'logarithmic',
                    grid: { color: colors.gridLines },
                    title: { display: true, text: `2026 예산 (${UNIT_LABEL})`, color: colors.textSecondary },
                    afterBuildTicks: logTicks,
                    ticks: { callback: v => [1,2,5].includes(v / Math.pow(10, Math.floor(Math.log10(v || 1)))) ? formatNum(v) : '' }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.97)',
                    titleColor: '#1e293b',
                    bodyColor: '#334155',
                    borderColor: 'rgba(0,0,0,0.12)',
                    borderWidth: 1,
                    callbacks: {
                        title: (items) => items[0].dataset.data[items[0].dataIndex].deptName,
                        label: (ctx) => {
                            const d = ctx.dataset.data[ctx.dataIndex];
                            const newRatio = ((d.newCount / ctx.parsed.x) * 100).toFixed(1);
                            return [
                                `사업 수: ${ctx.parsed.x}건`,
                                `예산 총액: ${formatNum(ctx.parsed.y)} ${UNIT_LABEL}`,
                                `신규사업: ${d.newCount}건 (${newRatio}%)`,
                                `증가예산: +${formatNum(d.incAmt)} ${UNIT_LABEL}`,
                                `감소예산: -${formatNum(d.decAmt)} ${UNIT_LABEL}`
                            ];
                        }
                    }
                }
            }
        },
        plugins: [avgLinesPlugin]
    });

    buildScatterDistTable(data);
}

function buildScatterDistTable(data) {
    // 부처명 → 상세 정보 맵
    const deptMap = {};
    data.dept_summary.forEach(d => { deptMap[d.dept_name] = d; });

    // 사업수 기준으로 부처 그룹화
    const groups = {};
    data.dept_summary.forEach(d => {
        const k = d.project_count;
        if (!groups[k]) groups[k] = { depts: [], totalBudget: 0 };
        groups[k].depts.push(d.dept_name);
        groups[k].totalBudget += d.budget_2026_mil || 0;
    });

    const tooltip = document.getElementById('dept-tooltip');

    function showTooltip(e, name) {
        const d = deptMap[name] || {};
        const budget = ((d.budget_2026_mil || 0) / 100000).toFixed(1);
        const perProj = d.project_count ? ((d.budget_2026_mil || 0) / d.project_count / 100000).toFixed(1) : '–';
        const newCount = d.new_count ?? 0;
        const newRate = d.project_count ? ((newCount / d.project_count) * 100).toFixed(1) : '–';
        tooltip.innerHTML =
            `<strong style="display:block;margin-bottom:4px;color:var(--accent-color)">${name}</strong>` +
            `사업수: <strong>${d.project_count}건</strong><br>` +
            `예산액: <strong>${budget}천억원</strong><br>` +
            `사업별 평균예산액: <strong>${perProj}천억원</strong><br>` +
            `신규사업수: <strong>${newCount}건 (${newRate}%)</strong>`;
        positionTooltip(e);
        tooltip.style.display = 'block';
    }

    function positionTooltip(e) {
        const pad = 12;
        const tw = tooltip.offsetWidth || 200;
        const th = tooltip.offsetHeight || 120;
        let x = e.clientX + pad;
        let y = e.clientY + pad;
        if (x + tw > window.innerWidth - pad) x = e.clientX - tw - pad;
        if (y + th > window.innerHeight - pad) y = e.clientY - th - pad;
        tooltip.style.left = x + 'px';
        tooltip.style.top  = y + 'px';
    }

    function hideTooltip() {
        tooltip.style.display = 'none';
    }

    const tbody = document.getElementById('scatterDistBody');
    Object.keys(groups)
        .map(Number)
        .sort((a, b) => a - b)
        .forEach(cnt => {
            const g = groups[cnt];
            const avgBudget = (g.totalBudget / g.depts.length / 100000).toFixed(1);

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="text-align:center; font-weight:600">${cnt}건</td>
                <td style="text-align:center">${g.depts.length}개</td>
                <td style="color:var(--text-secondary)" class="dept-names-cell"></td>
                <td style="text-align:right; font-weight:600">${avgBudget}</td>`;

            const cell = tr.querySelector('.dept-names-cell');
            g.depts.forEach((name, i) => {
                if (i > 0) cell.appendChild(document.createTextNode(', '));
                const span = document.createElement('span');
                span.className = 'dept-tip';
                span.textContent = name;
                span.addEventListener('mouseenter', e => showTooltip(e, name));
                span.addEventListener('mousemove',  e => positionTooltip(e));
                span.addEventListener('mouseleave', hideTooltip);
                cell.appendChild(span);
            });

            tbody.appendChild(tr);
        });
}

function setupDrilldown(data) {
    const select = document.getElementById('deptSelect');
    [...data.dept_summary].sort((a, b) => a.dept_name.localeCompare(b.dept_name)).forEach(d => {
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

        tr.innerHTML = `<td>${p.dept_name}</td>
            <td class="project-name-cell" style="font-weight:500">${p.project_name}</td>
            <td class="text-right">${formatNum(toUnit(p.budget_2024))}</td><td class="text-right">${formatNum(toUnit(p.budget_2025))}</td>
            <td class="text-right" style="color:var(--blue);font-weight:600">${formatNum(toUnit(p.budget_2026))}</td>
            <td class="text-right">${badge}</td><td class="text-center">${p.is_new ? '신규' : '계속'}</td>`;
        if (p.description) tr.querySelector('.project-name-cell').dataset.desc = p.description;
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
        if (type === 'new') {
            tr.innerHTML = `<td>${p.dept_name}</td>
                <td class="project-name-cell" style="font-weight:500">${p.project_name}</td>
                <td class="text-right" style="color:var(--green);font-weight:600">${formatNum(toUnit(p.budget_2026))}</td>`;
        } else {
            const isInc = type === 'increase';
            const cssColor = isInc ? 'var(--blue)' : 'var(--red)';
            const arrow = isInc ? '▲' : '▼';
            const rateStr = p.change_rate != null ? `${p.change_rate > 0 ? '+' : ''}${p.change_rate.toFixed(1)}%` : '-';
            tr.innerHTML = `<td>${p.dept_name}</td>
                <td class="project-name-cell" style="font-weight:500">${p.project_name}</td>
                <td class="text-right">${formatNum(toUnit(p.budget_2025))}</td>
                <td class="text-right">${formatNum(toUnit(p.budget_2026))}</td>
                <td class="text-right" style="color:${cssColor};font-weight:600">${arrow} ${formatNum(toUnit(Math.abs(p.change_amount)))}</td>
                <td class="text-right" style="color:${cssColor}">${rateStr}</td>`;
        }
        if (p.description) tr.querySelector('.project-name-cell').dataset.desc = p.description;
        tbody.appendChild(tr);
    });
}

// ======== Tooltip Cursor Tracking ========
function formatDescription(desc) {
    if (!desc) return '';
    // Insert newline before 2nd+ bullet characters
    return desc.replace(/([^\n])\s*([○●◦·▪◆▶])/g, '$1\n$2').trim();
}

function initTooltipTracking() {
    // Single shared tooltip appended directly to body — avoids backdrop-filter containing block issue
    const tip = document.createElement('div');
    tip.className = 'project-tooltip';
    document.body.appendChild(tip);
    let visible = false;

    function positionTooltip(cx, cy) {
        const w = 360, h = 220, vw = window.innerWidth, vh = window.innerHeight;
        const x = cx + 14, y = cy + 14;
        tip.style.left = (x + w > vw ? cx - w - 6 : x) + 'px';
        tip.style.top = (y + h > vh ? cy - h - 6 : y) + 'px';
    }

    document.addEventListener('mouseover', (e) => {
        const cell = e.target.closest('.project-name-cell');
        if (cell && cell.dataset.desc) {
            tip.textContent = formatDescription(cell.dataset.desc);
            positionTooltip(e.clientX, e.clientY);
            tip.style.display = 'block';
            visible = true;
        }
    });

    document.addEventListener('mousemove', (e) => {
        if (!visible) return;
        positionTooltip(e.clientX, e.clientY);
    });

    document.addEventListener('mouseout', (e) => {
        const cell = e.target.closest('.project-name-cell');
        if (cell && !cell.contains(e.relatedTarget)) {
            tip.style.display = 'none';
            visible = false;
        }
    });
}

// ======== TAB: 부처별 현황 ========
function renderDeptTab(data) {
    const select = document.getElementById('deptViewSelect');
    const topDept = data.dept_summary[0].dept_name;

    [...data.dept_summary].sort((a, b) => a.dept_name.localeCompare(b.dept_name)).forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.dept_name;
        opt.textContent = `${d.dept_name} (${d.project_count}건)`;
        if (d.dept_name === topDept) opt.selected = true;
        select.appendChild(opt);
    });

    select.addEventListener('change', () => updateDeptView(select.value));
    document.getElementById('deptSearchInput').addEventListener('input', () => {
        updateDeptProjectsTable(select.value, document.getElementById('deptSearchInput').value);
    });

    updateDeptView(topDept);
}

function updateDeptView(deptName) {
    const data = globalData;
    const dept = data.dept_summary.find(d => d.dept_name === deptName);
    if (!dept) return;

    // KPIs
    document.getElementById('dept-kpi-budget').innerText = formatNum(toUnit(dept.budget_2026_mil));
    document.getElementById('dept-kpi-count').innerText = dept.project_count + '건';
    document.getElementById('dept-kpi-count-detail').innerText = `신규 ${dept.new_count}건 포함`;

    const changeAmt = toUnit(dept.change_amount_mil);
    const arrow = changeAmt >= 0 ? '▲' : '▼';
    const changeClass = changeAmt >= 0 ? 'trend-up' : 'trend-down';
    document.getElementById('dept-kpi-change').className = `kpi-value ${changeClass}`;
    document.getElementById('dept-kpi-change').innerText = `${arrow} ${formatNum(Math.abs(changeAmt))}`;
    document.getElementById('dept-kpi-change-rate').innerText = `억원 (${dept.change_rate_pct > 0 ? '+' : ''}${dept.change_rate_pct.toFixed(1)}%)`;

    document.getElementById('dept-kpi-new').innerText = dept.new_count + '건';
    document.getElementById('dept-kpi-new-ratio').innerText = `전체의 ${((dept.new_count / dept.project_count) * 100).toFixed(1)}%`;

    // Composition donut (increased_count includes new projects)
    if (charts.deptComp) charts.deptComp.destroy();
    charts.deptComp = new Chart(document.getElementById('deptCompositionChart').getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: ['증가(계속)', '감소', '동결', '신규사업'],
            datasets: [{
                data: [
                    Math.max(0, dept.increased_count - dept.new_count),
                    dept.decreased_count,
                    dept.frozen_count,
                    dept.new_count
                ],
                backgroundColor: [colors.blueLight, colors.redLight, colors.grayLight, colors.greenLight],
                borderColor: [colors.blue, colors.red, colors.gray, colors.green],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: { position: 'right' },
                tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw}건` } }
            }
        }
    });

    // Yearly bar chart (dept total budget per year)
    const deptProjs = data.projects.filter(p => p.dept_name === deptName);
    const total2024 = toUnit(deptProjs.reduce((s, p) => s + (p.budget_2024 || 0), 0));
    const total2025 = toUnit(deptProjs.reduce((s, p) => s + (p.budget_2025 || 0), 0));
    const total2026 = toUnit(deptProjs.reduce((s, p) => s + (p.budget_2026 || 0), 0));

    if (charts.deptYearly) charts.deptYearly.destroy();
    charts.deptYearly = new Chart(document.getElementById('deptYearlyChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: ['2024 결산', '2025 예산', '2026 예산'],
            datasets: [{
                label: `예산 (${UNIT_LABEL})`,
                data: [total2024, total2025, total2026],
                backgroundColor: [colors.grayLight, colors.purpleLight, colors.blueLight],
                borderColor: [colors.gray, colors.purple, colors.blue],
                borderWidth: 1,
                borderRadius: 6
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
                tooltip: { callbacks: { label: ctx => `${formatNum(ctx.raw)} ${UNIT_LABEL}` } }
            }
        }
    });

    // Top 10 horizontal bar
    const top10 = [...deptProjs].sort((a, b) => (b.budget_2026 || 0) - (a.budget_2026 || 0)).slice(0, 10);
    renderHorizontalBar('deptTop10Chart', top10, p => toUnit(p.budget_2026), `2026 예산 (${UNIT_LABEL})`, colors.purpleLight, colors.purple,
        (ctx, i) => [`예산: ${formatNum(ctx.raw)} ${UNIT_LABEL}`, top10[i].is_new ? '신규사업' : '계속사업']);

    // Table
    updateDeptProjectsTable(deptName, document.getElementById('deptSearchInput').value);
}

function updateDeptProjectsTable(deptName, searchTerm) {
    let projs = globalData.projects.filter(p => p.dept_name === deptName);
    if (searchTerm) {
        const t = searchTerm.toLowerCase();
        projs = projs.filter(p => p.project_name.toLowerCase().includes(t));
    }
    projs.sort((a, b) => (b.budget_2026 || 0) - (a.budget_2026 || 0));

    const tbody = document.getElementById('deptProjectsTableBody');
    tbody.innerHTML = '';
    projs.forEach(p => {
        const tr = document.createElement('tr');
        const changeAmt = toUnit(p.change_amount || 0);
        const changeColor = p.is_new ? 'var(--green)' : (changeAmt > 0 ? 'var(--blue)' : changeAmt < 0 ? 'var(--red)' : 'var(--text-secondary)');
        const rateStr = p.is_new ? '-' : (p.change_rate != null ? `${p.change_rate > 0 ? '+' : ''}${p.change_rate.toFixed(1)}%` : '-');
        const changeStr = p.is_new ? '-' : (changeAmt >= 0 ? `▲ ${formatNum(changeAmt)}` : `▼ ${formatNum(Math.abs(changeAmt))}`);
        tr.innerHTML = `
            <td class="project-name-cell" style="font-weight:500">${p.project_name}</td>
            <td class="text-right">${formatNum(toUnit(p.budget_2024))}</td>
            <td class="text-right">${formatNum(toUnit(p.budget_2025))}</td>
            <td class="text-right" style="color:var(--blue);font-weight:600">${formatNum(toUnit(p.budget_2026))}</td>
            <td class="text-right" style="color:${changeColor};font-weight:600">${changeStr}</td>
            <td class="text-right" style="color:${changeColor}">${rateStr}</td>
            <td class="text-center">${p.is_new ? '<span class="badge badge-new">신규</span>' : '계속'}</td>`;
        if (p.description) tr.querySelector('.project-name-cell').dataset.desc = p.description;
        tbody.appendChild(tr);
    });
}

// ======== Chart Resize on Window Resize ========
// Chart.js responsive:true handles most cases, but grid reflow can miss resize events
let resizeTimer;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
        Object.values(charts).forEach(c => { if (c && typeof c.resize === 'function') c.resize(); });
    }, 100);
});

// Start
document.addEventListener('DOMContentLoaded', initDashboard);
