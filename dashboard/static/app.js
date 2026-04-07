/**
 * Arbitrage Monitor — Dashboard JS
 *
 * Uses SSE for real-time updates, falls back to polling.
 * - Tab 1: Opportunities table
 * - Tab 2: Kimchi premium heatmap
 * - Tab 3: History chart + table
 * - Tab 4: What-If simulator
 */

const API_BASE = '/api';
const POLL_INTERVAL = 5000;

// --- Tab navigation ---
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    item.classList.add('active');
    const tabId = item.dataset.tab;
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${tabId}`).classList.add('active');
  });
});

// --- Utility ---
function formatPct(val) {
  if (val == null) return '--';
  const num = parseFloat(val);
  const sign = num >= 0 ? '+' : '';
  return `${sign}${num.toFixed(2)}%`;
}

function pctClass(val) {
  if (val == null) return 'neutral';
  return parseFloat(val) >= 0 ? 'profit' : 'loss';
}

function riskBadge(level) {
  const cls = {LOW: 'badge-low', MED: 'badge-med', HIGH: 'badge-high'}[level] || 'badge-med';
  return `<span class="badge ${cls}">${level}</span>`;
}

function formatTime(ts) {
  if (!ts) return '--:--:--';
  const d = new Date(ts);
  return d.toLocaleTimeString('ko-KR', {hour12: false});
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function formatKRW(val) {
  if (val == null) return '--';
  return Math.round(val).toLocaleString('ko-KR') + '원';
}

function heatColor(pct) {
  if (pct >= 3) return 'rgba(14, 203, 129, 0.25)';
  if (pct >= 2) return 'rgba(14, 203, 129, 0.18)';
  if (pct >= 1) return 'rgba(14, 203, 129, 0.12)';
  if (pct >= 0) return 'rgba(14, 203, 129, 0.05)';
  if (pct >= -1) return 'rgba(246, 70, 93, 0.08)';
  if (pct >= -2) return 'rgba(246, 70, 93, 0.15)';
  return 'rgba(246, 70, 93, 0.22)';
}

async function fetchJSON(path) {
  try {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error(`API error ${path}:`, e);
    return null;
  }
}

// --- Previous values for flash detection ---
let prevSpreads = {};

// --- Tab 1: Opportunities ---
let selectedOpp = null;

function renderOpportunities(opps) {
  const tbody = document.getElementById('opp-table-body');
  const empty = document.getElementById('opp-empty');
  const count = document.getElementById('opp-count');

  count.textContent = `기회 ${opps.length}개`;

  if (opps.length === 0) {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  tbody.innerHTML = opps.map((opp, i) => `
    <tr class="row-enter${selectedOpp === i ? ' selected' : ''}" data-idx="${i}" onclick="selectOpp(${i})">
      <td style="font-size: 12px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${opp.path}</td>
      <td>${opp.hops}</td>
      <td class="${pctClass(opp.net_profit)}">${formatPct(opp.net_profit)}</td>
      <td class="${pctClass(opp.gross_spread)}">${formatPct(opp.gross_spread)}</td>
      <td>${opp.total_fees != null ? opp.total_fees.toFixed(2) + '%' : '--'}</td>
      <td>${riskBadge(opp.risk_level)}</td>
    </tr>
  `).join('');

  window._opps = opps;
}

function selectOpp(idx) {
  selectedOpp = idx;
  const panel = document.getElementById('opp-detail');
  const opp = window._opps?.[idx];
  if (!opp) { panel.classList.remove('open'); return; }

  panel.classList.add('open');

  const pathParts = opp.path.split('->');
  document.getElementById('detail-path').innerHTML = pathParts.map((p, i) =>
    `<span class="path-node">${p}</span>${i < pathParts.length - 1 ? '<span class="path-arrow">\u2192</span>' : ''}`
  ).join('');

  document.getElementById('detail-stats').innerHTML = `
    <div class="stat-box">
      <div class="stat-label">순수익률</div>
      <div class="stat-value ${pctClass(opp.net_profit)}">${formatPct(opp.net_profit)}</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">총수익률</div>
      <div class="stat-value ${pctClass(opp.gross_spread)}">${formatPct(opp.gross_spread)}</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">수수료</div>
      <div class="stat-value">${opp.total_fees?.toFixed(2) ?? '--'}%</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">리스크</div>
      <div class="stat-value">${riskBadge(opp.risk_level)}</div>
    </div>
  `;
}

// --- Tab 2: Premium Heatmap ---
function renderSpreads(spreads) {
  const grid = document.getElementById('heatmap-grid');

  if (spreads.length > 0 && spreads[0].implied_rate) {
    document.getElementById('rate-display').textContent =
      `환율: ${spreads[0].implied_rate.toFixed(0)} KRW/USDT`;
  }

  grid.innerHTML = spreads.map(s => {
    const pct = s.net_spread_pct;
    const arrow = pct >= 0 ? '\u25B2' : '\u25BC';

    // Flash detection
    let flashClass = '';
    const prevPct = prevSpreads[s.symbol];
    if (prevPct !== undefined && prevPct !== pct) {
      flashClass = pct > prevPct ? 'flash-up' : 'flash-down';
    }
    prevSpreads[s.symbol] = pct;

    return `
      <div class="heat-cell ${flashClass}" style="background: ${heatColor(pct)}">
        <div class="symbol">${s.symbol}</div>
        <div class="pct ${pctClass(pct)}">${arrow} ${formatPct(pct)}</div>
        <div class="detail">
          U: ${s.upbit_bid?.toLocaleString() ?? '--'}<br>
          B: ${s.binance_ask?.toFixed(2) ?? '--'}
        </div>
      </div>
    `;
  }).join('');
}

// --- Tab 3: History ---
let historyChart = null;

async function refreshHistory() {
  const data = await fetchJSON('/history');
  if (!data) return;

  const hist = data.history || [];
  const tbody = document.getElementById('history-table-body');

  tbody.innerHTML = hist.slice(0, 50).map(h => `
    <tr>
      <td>${formatTime(h.timestamp)}</td>
      <td style="font-size: 12px; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${h.path}</td>
      <td class="${pctClass(h.net_profit)}">${formatPct(h.net_profit)}</td>
      <td>${riskBadge(h.risk_level)}</td>
    </tr>
  `).join('');

  updateHistoryChart(hist);
}

function updateHistoryChart(hist) {
  const canvas = document.getElementById('history-chart');
  if (!canvas) return;

  const hourly = {};
  hist.forEach(h => {
    const d = new Date(h.timestamp);
    const hourKey = `${d.getHours().toString().padStart(2, '0')}:00`;
    if (!hourly[hourKey]) hourly[hourKey] = { count: 0, totalProfit: 0 };
    hourly[hourKey].count++;
    hourly[hourKey].totalProfit += h.net_profit || 0;
  });

  const labels = Object.keys(hourly).sort();
  const counts = labels.map(l => hourly[l].count);
  const avgProfit = labels.map(l => hourly[l].count > 0 ? hourly[l].totalProfit / hourly[l].count : 0);

  if (historyChart) historyChart.destroy();

  historyChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: '기회 수',
          data: counts,
          backgroundColor: 'rgba(240, 185, 11, 0.4)',
          borderColor: '#F0B90B',
          borderWidth: 1,
          yAxisID: 'y',
        },
        {
          label: '평균 수익률 (%)',
          data: avgProfit,
          type: 'line',
          borderColor: '#0ECB81',
          backgroundColor: 'rgba(14, 203, 129, 0.1)',
          borderWidth: 2,
          pointRadius: 3,
          yAxisID: 'y1',
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#B7BDC6', font: { family: 'Geist', size: 11 } } },
      },
      scales: {
        x: {
          ticks: { color: '#848E9C', font: { family: 'Geist Mono', size: 11 } },
          grid: { color: '#2B3139' },
        },
        y: {
          position: 'left',
          ticks: { color: '#848E9C', font: { family: 'Geist Mono', size: 11 } },
          grid: { color: '#2B3139' },
          title: { display: true, text: '기회 수', color: '#848E9C' },
        },
        y1: {
          position: 'right',
          ticks: { color: '#848E9C', font: { family: 'Geist Mono', size: 11 } },
          grid: { drawOnChartArea: false },
          title: { display: true, text: '평균 수익률 %', color: '#848E9C' },
        },
      },
    },
  });
}

// --- Tab 4: What-If Simulator ---
async function runWhatIf() {
  const amount = parseFloat(document.getElementById('whatif-amount').value) || 1000000;
  const feeInput = document.getElementById('whatif-fee').value;
  const fee = feeInput ? parseFloat(feeInput) / 100 : null;
  const slippage = parseFloat(document.getElementById('whatif-slippage').value) || 0.1;

  const body = {
    amount_krw: amount,
    slippage_pct: slippage,
  };
  if (fee !== null) body.fee_override = fee;

  const btn = document.getElementById('whatif-run');
  btn.disabled = true;
  btn.textContent = '계산 중...';

  try {
    const res = await fetch(`${API_BASE}/whatif`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await res.json();

    if (data.error) {
      document.getElementById('whatif-results').innerHTML =
        `<div class="empty-state"><p>${data.error}</p></div>`;
      return;
    }

    const sims = data.simulations || [];
    if (sims.length === 0) {
      document.getElementById('whatif-results').innerHTML =
        '<div class="empty-state"><p>시뮬레이션 결과가 없습니다.</p></div>';
      return;
    }

    document.getElementById('whatif-results').innerHTML = `
      <table>
        <thead>
          <tr>
            <th>코인</th>
            <th>투자금</th>
            <th>회수금</th>
            <th>순이익</th>
            <th>수익률</th>
            <th>수수료</th>
          </tr>
        </thead>
        <tbody>
          ${sims.map(s => `
            <tr>
              <td style="font-weight: 600;">${s.symbol}</td>
              <td>${formatKRW(s.amount_krw)}</td>
              <td>${formatKRW(s.krw_received)}</td>
              <td class="${pctClass(s.gross_profit_krw)}">${formatKRW(s.gross_profit_krw)}</td>
              <td class="${pctClass(s.net_profit_pct)}">${formatPct(s.net_profit_pct)}</td>
              <td>${formatKRW(s.fees_krw)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      <div style="margin-top: 8px; font-size: 11px; color: var(--text-muted);">
        환율: ${sims[0].implied_rate?.toLocaleString() ?? '--'} KRW/USDT | 슬리피지: ${sims[0].slippage_pct}%
      </div>
    `;
  } catch (e) {
    document.getElementById('whatif-results').innerHTML =
      `<div class="empty-state"><p>오류: ${e.message}</p></div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '시뮬레이션 실행';
  }
}

// Update slider display values
function setupSlider(id, displayId, suffix) {
  const slider = document.getElementById(id);
  const display = document.getElementById(displayId);
  if (slider && display) {
    slider.addEventListener('input', () => {
      display.textContent = slider.value + suffix;
    });
  }
}

// --- Status ---
function renderStatus(data) {
  if (!data) {
    document.getElementById('status-dot').className = 'status-dot offline';
    document.getElementById('status-text').textContent = '연결 끊김';
    return;
  }

  document.getElementById('status-dot').className = 'status-dot online';
  document.getElementById('status-text').textContent = '연결됨';
  document.getElementById('last-update').textContent = `마지막 갱신: ${formatTime(data.last_update)}`;
  document.getElementById('footer-interval').textContent = data.polling_interval || 3;
  document.getElementById('footer-coins').textContent = data.target_coins?.length || 0;
  document.getElementById('footer-db-size').textContent = formatBytes(data.db_size_bytes || 0);
}

// --- SSE Connection ---
let sseConnected = false;

function connectSSE() {
  const evtSource = new EventSource(`${API_BASE}/stream`);

  evtSource.addEventListener('opportunities', (e) => {
    try {
      const data = JSON.parse(e.data);
      renderOpportunities(data.opportunities || []);
    } catch (err) { console.error('SSE opportunities parse error:', err); }
  });

  evtSource.addEventListener('spreads', (e) => {
    try {
      const data = JSON.parse(e.data);
      renderSpreads(data.spreads || []);
    } catch (err) { console.error('SSE spreads parse error:', err); }
  });

  evtSource.addEventListener('status', (e) => {
    try {
      renderStatus(JSON.parse(e.data));
    } catch (err) { console.error('SSE status parse error:', err); }
  });

  evtSource.onopen = () => {
    sseConnected = true;
    console.log('SSE connected');
  };

  evtSource.onerror = () => {
    sseConnected = false;
    evtSource.close();
    // Reconnect after 5 seconds
    setTimeout(connectSSE, 5000);
  };
}

// --- Polling fallback (initial load + history) ---
async function initialLoad() {
  const [opps, spreads, status] = await Promise.all([
    fetchJSON('/opportunities'),
    fetchJSON('/spreads'),
    fetchJSON('/status'),
  ]);

  if (opps) renderOpportunities(opps.opportunities || []);
  if (spreads) renderSpreads(spreads.spreads || []);
  renderStatus(status);
}

// --- Init ---
initialLoad();
connectSSE();

// History refresh on tab switch (not via SSE — less frequent)
document.querySelector('[data-tab="history"]').addEventListener('click', () => {
  setTimeout(refreshHistory, 100);
});

// Periodic history refresh when tab is active
setInterval(() => {
  const historyTab = document.getElementById('tab-history');
  if (historyTab.classList.contains('active')) {
    refreshHistory();
  }
}, 15000);

// Fallback polling if SSE disconnects
setInterval(async () => {
  if (!sseConnected) {
    await initialLoad();
  }
}, POLL_INTERVAL);

// What-If slider displays
const amountSlider = document.getElementById('whatif-amount');
const amountDisplay = document.getElementById('amount-display');
if (amountSlider && amountDisplay) {
  amountSlider.addEventListener('input', () => {
    amountDisplay.textContent = parseInt(amountSlider.value).toLocaleString('ko-KR');
  });
}

const feeSlider = document.getElementById('whatif-fee');
const feeDisplay = document.getElementById('fee-display');
if (feeSlider && feeDisplay) {
  feeSlider.addEventListener('input', () => {
    feeDisplay.textContent = feeSlider.value ? feeSlider.value + '%' : '기본값';
  });
}

const slippageSlider = document.getElementById('whatif-slippage');
const slippageDisplay = document.getElementById('slippage-display');
if (slippageSlider && slippageDisplay) {
  slippageSlider.addEventListener('input', () => {
    slippageDisplay.textContent = parseFloat(slippageSlider.value).toFixed(2) + '%';
  });
}
