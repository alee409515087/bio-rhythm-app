/* ── Bio-Rhythm Dashboard JS ─────────────────────────────────── */
const DAYS  = ['週一','週二','週三','週四','週五','週六','週日'];
const HOURS = Array.from({length: 15}, (_, i) => i + 7); // 07–21

/* ── Color scale: red → amber → green ───────────────────────── */
function scoreToColor(score) {
  if (score === null || score === undefined) return null;
  const s = Math.max(0, Math.min(100, score));
  let r, g, b;
  if (s < 50) {
    const t = s / 50;
    r = 255; g = Math.round(82 + t * (179 - 82)); b = Math.round(82 + t * (0 - 82));
  } else {
    const t = (s - 50) / 50;
    r = Math.round(255 + t * (0 - 255));
    g = Math.round(179 + t * (230 - 179));
    b = Math.round(0   + t * (118 - 0));
  }
  return `rgb(${r},${g},${b})`;
}

function scoreLabel(s) {
  if (s === null) return '—';
  return s >= 75 ? '高效能' : s >= 45 ? '中效能' : '低效能';
}

/* ── Heatmap: X = hours, Y = days ───────────────────────────── */
function renderHeatmap(data) {
  const container = document.getElementById('heatmapContainer');
  const loading   = document.getElementById('heatmapLoading');

  // Build lookup
  const lookup = {};
  let totalScore = 0, totalCount = 0, cellCount = 0;
  let bestScore = -1, bestDay = null, bestHour = null;
  data.forEach(d => {
    lookup[`${d.day}_${d.hour}`] = d;
    if (d.score !== null) {
      totalScore += d.score; totalCount += d.count || 0; cellCount++;
      if (d.score > bestScore) { bestScore = d.score; bestDay = d.day; bestHour = d.hour; }
    }
  });

  // Update header stats
  const avgEl  = document.getElementById('statAvg');
  const peakEl = document.getElementById('statPeak');
  const sessEl = document.getElementById('statSessions');
  if (avgEl)  avgEl.textContent  = cellCount ? (totalScore / cellCount).toFixed(1) : '—';
  if (peakEl) peakEl.textContent = bestDay !== null ? `${DAYS[bestDay]} ${bestHour}:00` : '—';
  if (sessEl) sessEl.textContent = totalCount;

  /*
   * Grid layout: X-axis = hours (columns), Y-axis = days (rows)
   * Columns: [day-label] + [hour0] [hour1] ... [hourN]
   * Rows:    [header row with hour labels] then [day rows]
   */
  const numCols = HOURS.length;
  // Set grid-template-columns: day-label col + one col per hour
  container.style.gridTemplateColumns = `52px repeat(${numCols}, minmax(38px, 1fr))`;

  let html = '';

  // Row 0: top-left blank corner + hour headers
  html += '<div class="hm-corner"></div>';
  HOURS.forEach(h => {
    html += `<div class="hm-hour-header">${String(h).padStart(2,'0')}</div>`;
  });

  // Rows 1–7: one row per day
  for (let day = 0; day < 7; day++) {
    // Day label
    html += `<div class="hm-day-label">${DAYS[day]}</div>`;
    // Hour cells
    HOURS.forEach(hour => {
      const key   = `${day}_${hour}`;
      const cell  = lookup[key];
      const score = cell ? cell.score : null;
      const count = cell ? cell.count : 0;
      const color = scoreToColor(score);

      if (color) {
        html += `<div class="hm-cell cell-score"
          style="background:${color}"
          data-day="${day}" data-hour="${hour}"
          data-score="${score.toFixed(1)}" data-count="${count}"></div>`;
      } else {
        html += `<div class="hm-cell no-data"
          data-day="${day}" data-hour="${hour}"
          data-score="" data-count="0"></div>`;
      }
    });
  }

  container.innerHTML = html;
  loading.style.display = 'none';
  container.style.display = 'grid';

  // Tooltip events
  const tooltip = document.getElementById('tooltip');
  container.querySelectorAll('.hm-cell').forEach(cell => {
    cell.addEventListener('mousemove', e => {
      const day   = parseInt(cell.dataset.day);
      const hour  = parseInt(cell.dataset.hour);
      const score = cell.dataset.score;
      const count = cell.dataset.count;
      if (score !== '') {
        const s = parseFloat(score);
        tooltip.innerHTML = `
          <div class="tooltip-score" style="color:${scoreToColor(s)}">${s.toFixed(1)}</div>
          <div class="tooltip-label">${DAYS[day]}・${String(hour).padStart(2,'0')}:00 – ${String(hour+1).padStart(2,'0')}:00</div>
          <div class="tooltip-detail">資料點：${count} 次 · ${scoreLabel(s)}</div>`;
      } else {
        tooltip.innerHTML = `
          <div class="tooltip-score" style="color:var(--text-dim)">—</div>
          <div class="tooltip-label">${DAYS[day]}・${String(hour).padStart(2,'0')}:00</div>
          <div class="tooltip-detail">尚無學習紀錄</div>`;
      }
      tooltip.classList.add('visible');
      positionTooltip(e);
    });
    cell.addEventListener('mousemove', e => positionTooltip(e));
    cell.addEventListener('mouseleave', () => tooltip.classList.remove('visible'));
  });
}

function positionTooltip(e) {
  const tooltip = document.getElementById('tooltip');
  const tw = 190, th = 85;
  let x = e.clientX + 14, y = e.clientY - 20;
  if (x + tw > window.innerWidth  - 10) x = e.clientX - tw - 14;
  if (y + th > window.innerHeight - 10) y = e.clientY - th - 10;
  tooltip.style.left = x + 'px';
  tooltip.style.top  = y + 'px';
}

/* ── Insights renderer ───────────────────────────────────────── */
function renderInsights(insights) {
  const grid = document.getElementById('insightsGrid');
  if (!insights || !insights.length) {
    grid.innerHTML = '<div class="insight-loading">尚無洞察資料</div>';
    return;
  }
  grid.innerHTML = insights.map(ins => `
    <div class="insight-item type-${ins.type}">
      <div class="insight-icon">${ins.icon}</div>
      <div class="insight-body">
        <div class="insight-title">${ins.title}</div>
        <div class="insight-text">${ins.body}</div>
      </div>
    </div>`).join('');
}

/* ── Data fetch ──────────────────────────────────────────────── */
async function fetchData(filterType, filterId) {
  const loading   = document.getElementById('heatmapLoading');
  const container = document.getElementById('heatmapContainer');
  const insGrid   = document.getElementById('insightsGrid');

  loading.style.display = 'flex';
  container.style.display = 'none';
  insGrid.innerHTML = '<div class="insight-loading"><span class="loading-spin">◌</span> 分析中…</div>';

  const p = new URLSearchParams({ type: filterType });
  if (filterId) p.set('id', filterId);

  const [heatData, insData] = await Promise.all([
    fetch(`/api/heatmap?${p}`).then(r => r.json()),
    fetch(`/api/insights?${p}`).then(r => r.json()),
  ]);

  renderHeatmap(heatData);
  renderInsights(insData);
}

/* ── 3-Layer filter (Branch → Team → Agent) ──────────────────── */
function initManagerFilters() {
  const branchSel = document.getElementById('branchSelect');
  const teamSel   = document.getElementById('teamSelect');
  const agentSel  = document.getElementById('agentSelect');
  const applyBtn  = document.getElementById('applyFilter');
  if (!branchSel) return;

  const allTeamOpts  = Array.from(teamSel.options).slice(1);
  const allAgentOpts = Array.from(agentSel.options).slice(1);

  function rebuildTeams(branchId) {
    while (teamSel.options.length > 1) teamSel.remove(1);
    allTeamOpts.forEach(o => {
      if (!branchId || o.dataset.branch === branchId) teamSel.add(o.cloneNode(true));
    });
    teamSel.value = '';
  }

  function rebuildAgents(branchId, teamId) {
    while (agentSel.options.length > 1) agentSel.remove(1);
    allAgentOpts.forEach(o => {
      const branchOk = !branchId || o.dataset.branch === branchId;
      const teamOk   = !teamId   || o.dataset.team   === teamId;
      if (branchOk && teamOk) agentSel.add(o.cloneNode(true));
    });
    agentSel.value = '';
  }

  branchSel.addEventListener('change', () => {
    rebuildTeams(branchSel.value);
    rebuildAgents(branchSel.value, '');
    updateLabel();
  });

  teamSel.addEventListener('change', () => {
    rebuildAgents(branchSel.value, teamSel.value);
    updateLabel();
  });

  function updateLabel() {
    const lbl = document.getElementById('viewLabel');
    if (!lbl) return;
    const bName = branchSel.options[branchSel.selectedIndex]?.text || '全部分行';
    const tName = teamSel.options[teamSel.selectedIndex]?.text   || '全部小組';
    const aName = agentSel.options[agentSel.selectedIndex]?.text || '全部業務員';
    lbl.textContent = `${bName} — ${tName} — ${aName}`;
  }

  applyBtn.addEventListener('click', () => {
    const agentId  = agentSel.value;
    const teamId   = teamSel.value;
    const branchId = branchSel.value;

    let ft = 'all', fid = null;
    if      (agentId)  { ft = 'agent';  fid = agentId; }
    else if (teamId)   { ft = 'team';   fid = teamId; }
    else if (branchId) { ft = 'branch'; fid = branchId; }

    updateLabel();
    fetchData(ft, fid);
  });
}

/* ── Entry point ─────────────────────────────────────────────── */
function initDashboard({ role }) {
  if (role === 'manager') {
    initManagerFilters();
    fetchData('all', null);
  } else {
    fetchData('agent', null);
  }
}
