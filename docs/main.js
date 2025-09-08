                    // ===== Config / State =====
                    const CSV_PATH = './data/leaderboard_history.csv';
                    const CSV_URL = `${CSV_PATH}?ts=${Date.now()}`; // cache-buster
                    const PREFS_KEY = 'gt_admin_dashboard_prefs_v1';

                    const state = {
                              rows: [],
                              latestRows: [],
                              latestRun: null,
                              prevRun: null,
                              topLimit: 10,
                              lastRuns: 8,
                              search: '',
                    };

                    // ===== Utilities =====
                    function savePrefs() {
                              try {
                                        localStorage.setItem(PREFS_KEY, JSON.stringify({ topLimit: state.topLimit, lastRuns: state.lastRuns, search: state.search }));
                              } catch { }
                    }
                    function loadPrefs() {
                              try {
                                        const p = JSON.parse(localStorage.getItem(PREFS_KEY) || '{}');
                                        if (p.topLimit) state.topLimit = p.topLimit;
                                        if (p.lastRuns) state.lastRuns = p.lastRuns;
                                        if (typeof p.search === 'string') state.search = p.search;
                              } catch { }
                              // reflect UI
                              document.getElementById('topN').value = String(state.topLimit);
                              document.getElementById('lastRuns').value = String(state.lastRuns);
                              document.getElementById('searchBox').value = state.search;
                    }
                    function fmtDate(iso) { try { return new Date(iso).toISOString().slice(0, 10); } catch { return iso; } }
                    function groupBy(arr, keyFn) {
                              const m = new Map();
                              for (const item of arr) {
                                        const k = keyFn(item);
                                        if (!m.has(k)) m.set(k, []);
                                        m.get(k).push(item);
                              }
                              return m;
                    }
                    const debounce = (fn, ms = 200) => {
                              let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
                    };
                    function percentile(arr, p) {
                              if (!arr.length) return 0;
                              const a = [...arr].sort((x, y) => x - y);
                              const idx = Math.min(a.length - 1, Math.max(0, Math.floor((p / 100) * (a.length - 1))));
                              return a[idx];
                    }

                    // Robust fetch with timeout + retry
                    async function fetchWithRetry(url, { timeout = 8000, retries = 2 } = {}) {
                              for (let attempt = 0; attempt <= retries; attempt++) {
                                        const ctrl = new AbortController();
                                        const id = setTimeout(() => ctrl.abort(), timeout);
                                        try {
                                                  const res = await fetch(url, { cache: 'no-store', signal: ctrl.signal });
                                                  clearTimeout(id);
                                                  if (res.ok) return res;
                                                  if (attempt === retries) throw new Error('HTTP ' + res.status);
                                        } catch (e) {
                                                  clearTimeout(id);
                                                  if (attempt === retries) throw e;
                                                  await new Promise(r => setTimeout(r, 600 * (attempt + 1)));
                                        }
                              }
                    }

                    // ===== Data load / compute =====
                    async function loadCSV() {
                              const res = await fetchWithRetry(CSV_URL, { timeout: 10000, retries: 2 });
                              const text = await res.text();
                              const parsed = Papa.parse(text.trim(), { header: true });
                              return parsed.data
                                        .filter(r => r.run_at_utc && r.admin_name)
                                        .map(r => ({
                                                  run_at_utc: r.run_at_utc,
                                                  week_label: r.week_label || 'last-7d',
                                                  admin_name: r.admin_name,
                                                  minutes: Number(r.minutes || 0)
                                        }));
                    }

                    function computeLatestAndPrev(rows) {
                              const byRun = groupBy(rows, r => r.run_at_utc);
                              const runs = Array.from(byRun.keys()).sort(); // ISO order
                              const latest = runs[runs.length - 1];
                              const prev = runs.length > 1 ? runs[runs.length - 2] : null;
                              const latestRows = byRun.get(latest).sort((a, b) => b.minutes - a.minutes);
                              const prevRows = prev ? byRun.get(prev) : [];

                              const prevMap = new Map(prevRows.map(r => [r.admin_name, r.minutes]));
                              const enriched = latestRows.map(r => {
                                        const prevMins = prevMap.get(r.admin_name) ?? 0;
                                        return { ...r, delta: r.minutes - prevMins };
                              });

                              return { latest, prev, latestRows: enriched, byRun, runKeys: runs };
                    }

                    function filtered(rows) {
                              const q = state.search.trim().toLowerCase();
                              if (!q) return rows;
                              return rows.filter(r => r.admin_name.toLowerCase().includes(q));
                    }

                    // ===== Rendering =====
                    function renderStats(latestRows) {
                              const mins = latestRows.map(r => r.minutes);
                              const total = mins.reduce((a, b) => a + b, 0);
                              const median = percentile(mins, 50);
                              const p90 = percentile(mins, 90);
                              document.getElementById('statAdmins').textContent = String(latestRows.length);
                              document.getElementById('statTotal').textContent = String(total);
                              document.getElementById('statMedian').textContent = String(median);
                              document.getElementById('statP90').textContent = String(p90);
                    }

                    function renderQuick(latestRows) {
                              const el = document.getElementById('quickStats');
                              if (!el) return;
                              el.textContent = `Players: ${latestRows.length} | CPU: —`;
                    }

                    function renderStatusPanel(latestIso) {
                              const panel = document.getElementById('statusPanel');
                              if (!panel) return;
                              panel.innerHTML = `<div class="card"><h3>Server</h3><p>Last run: ${fmtDate(latestIso)}</p></div>`;
                    }

                    function renderLatestTable(latestRows) {
                              const tbody = document.querySelector('#latestTable tbody');
                              tbody.innerHTML = '';
                              const top = filtered(latestRows).slice(0, state.topLimit);

                              top.forEach((r, i) => {
                                        const badgeClass = r.delta > 0 ? 'up' : (r.delta < 0 ? 'down' : 'flat');
                                        const sign = r.delta > 0 ? '+' : '';
                                        const tr = document.createElement('tr');
                                        tr.innerHTML = `
          <td>${i + 1}</td>
          <td>${r.admin_name}</td>
          <td>${r.minutes}</td>
          <td><span class="badge ${badgeClass}">${sign}${r.delta}</span></td>
        `;
                                        tbody.appendChild(tr);
                              });
                    }

                    function renderBarTop(latestRows, latestIso) {
                              const el = document.getElementById('barTop');
                              if (window._bar) window._bar.destroy();
                              const top = filtered(latestRows).slice(0, state.topLimit);
                              const labels = top.map(r => r.admin_name);
                              const data = top.map(r => r.minutes);
                              window._bar = new Chart(el, {
                                        type: 'bar',
                                        data: { labels, datasets: [{ label: 'Minutes', data, borderWidth: 1 }] },
                                        options: { responsive: true, plugins: { legend: { display: false } } }
                              });
                              document.getElementById('latestLabel').textContent = 'Week of run: ' + fmtDate(latestIso);
                              document.getElementById('lastUpdated').textContent = fmtDate(latestIso);
                              document.getElementById('downloadCsv').href = CSV_PATH;
                    }

                    function renderTrend(rows, latestRows, byRun, runKeys) {
                              const el = document.getElementById('lineTrend');
                              if (window._line) window._line.destroy();

                              const topAdmins = filtered(latestRows).slice(0, state.topLimit).map(r => r.admin_name);
                              const tail = runKeys.slice(-state.lastRuns);
                              const labels = tail.map(fmtDate);

                              const datasets = topAdmins.map(name => {
                                        const data = tail.map(run => {
                                                  const row = (byRun.get(run) || []).find(rr => rr.admin_name === name);
                                                  return row ? row.minutes : 0;
                                        });
                                        return { label: name, data, borderWidth: 2, fill: false };
                              });

                              window._line = new Chart(el, { type: 'line', data: { labels, datasets }, options: { responsive: true } });
                    }

                    // Sorting + a11y
                    let currentSort = { key: 'minutes', dir: 'desc' };
                    function sortRows(rows) {
                              const sorted = [...rows];
                              const { key, dir } = currentSort;
                              sorted.sort((a, b) => {
                                        if (key === 'minutes' || key === 'delta') return dir === 'asc' ? (a[key] - b[key]) : (b[key] - a[key]);
                                        if (key === 'admin') return dir === 'asc' ? a.admin_name.localeCompare(b.admin_name) : b.admin_name.localeCompare(a.admin_name);
                                        return 0;
                              });
                              return sorted;
                    }
                    function updateAriaSort() {
                              const map = { 'minutes': 'minutes', 'delta': 'delta', 'admin': 'admin' };
                              document.querySelectorAll('#latestTable th.sortable').forEach(th => {
                                        const key = th.getAttribute('data-key');
                                        const logical = key === 'rank' ? 'minutes' : (map[key] || key);
                                        th.setAttribute('aria-sort', logical === currentSort.key ? (currentSort.dir === 'asc' ? 'ascending' : 'descending') : 'none');
                              });
                    }
                    function attachSortHandlers() {
                              document.querySelectorAll('#latestTable th.sortable').forEach(th => {
                                        th.addEventListener('click', (ev) => {
                                                  const key = th.getAttribute('data-key');
                                                  const map = { rank: 'minutes', admin: 'admin', minutes: 'minutes', delta: 'delta' };
                                                  const nextKey = map[key] || 'minutes';
                                                  if (currentSort.key === nextKey) {
                                                            currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
                                                  } else {
                                                            currentSort.key = nextKey; currentSort.dir = nextKey === 'admin' ? 'asc' : 'desc';
                                                  }
                                                  updateAriaSort();
                                                  refresh();
                                        });
                              });
                              updateAriaSort();
                    }

                    // Controls
                    function attachControls() {
                              document.getElementById('topN').addEventListener('change', e => {
                                        state.topLimit = parseInt(e.target.value, 10);
                                        savePrefs(); refresh();
                              });
                              document.getElementById('lastRuns').addEventListener('change', e => {
                                        state.lastRuns = parseInt(e.target.value, 10);
                                        savePrefs(); refresh();
                              });
                              document.getElementById('searchBox').addEventListener('input', debounce(e => {
                                        state.search = e.target.value;
                                        savePrefs(); refresh();
                              }, 180));

                              // Downloads/exports
                              document.getElementById('downloadLatest').addEventListener('click', () => {
                                        const top = filtered(state.latestRows);
                                        const csv = 'admin_name,minutes\r\n' + top.map(r => `"${r.admin_name.replace(/"/g, '""')}",${r.minutes}`).join('\r\n');
                                        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url; a.download = `latest_${fmtDate(state.latestRun)}.csv`; a.click();
                                        URL.revokeObjectURL(url);
                              });
                              document.getElementById('exportBar').addEventListener('click', () => {
                                        if (!window._bar) return;
                                        const a = document.createElement('a');
                                        a.href = window._bar.toBase64Image('image/png', 1);
                                        a.download = `top_${fmtDate(state.latestRun)}.png`; a.click();
                              });
                              document.getElementById('exportLine').addEventListener('click', () => {
                                        if (!window._line) return;
                                        const a = document.createElement('a');
                                        a.href = window._line.toBase64Image('image/png', 1);
                                        a.download = `trend_${fmtDate(state.latestRun)}.png`; a.click();
                              });
                    }

                    function refresh() {
                              const sorted = sortRows(state.latestRows);
                              renderBarTop(sorted, state.latestRun);
                              renderLatestTable(sorted);
                              renderStats(sorted);
                              renderTrend(state.rows, sorted, state._byRun, state._runKeys);
                              renderQuick(sorted);
                              renderStatusPanel(state.latestRun);
                    }

                    // ===== Init =====
                    (async function init() {
                              try {
                                        loadPrefs();
                                        document.getElementById('messages').textContent = 'Loading data…';
                                        const rows = await loadCSV();
                                        state.rows = rows;
                                        if (!rows.length) {
                                                  document.getElementById('messages').innerHTML = '<div class="notice">No data yet. Run the scraper once to generate CSVs in <code>docs/data/</code>.</div>';
                                                  return;
                                        }
                                        const { latest, prev, latestRows, byRun, runKeys } = computeLatestAndPrev(rows);
                                        state.latestRun = latest;
                                        state.prevRun = prev;
                                        state.latestRows = latestRows;
                                        state._byRun = byRun;
                                        state._runKeys = runKeys;

                                        attachControls();
                                        attachSortHandlers();
                                        refresh();

                                        document.getElementById('messages').textContent = '';
                              } catch (e) {
                                        console.error(e);
                                        document.getElementById('messages').innerHTML = '<div class="notice">Error loading data (CSV not found or network issue). Ensure files exist under <code>docs/data/</code>.</div>';
                              }
                    })();
