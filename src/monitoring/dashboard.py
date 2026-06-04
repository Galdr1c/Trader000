"""Live HTML Dashboard — real-time monitoring for SVTR Bot.

Serves a beautiful, auto-refreshing dashboard at GET /
that displays: bot status, alerts, metrics, social tools,
exchange connection, AI status, and trade history.
"""

from __future__ import annotations

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SVTR Bot Dashboard</title>
<style>
:root {
  --bg: #0f1117; --surface: #1a1d27; --surface2: #232733;
  --border: #2d3142; --text: #e1e4ed; --text2: #8b8fa3;
  --green: #22c55e; --red: #ef4444; --yellow: #eab308; --blue: #3b82f6;
  --purple: #a855f7; --cyan: #06b6d4; --orange: #f97316;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', -apple-system, system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }
.header { background: linear-gradient(135deg, #1a1d27 0%, #0f1117 100%); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.header h1 { font-size: 20px; font-weight: 600; }
.header h1 span { color: var(--purple); }
.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 8px; animation: pulse 2s infinite; }
.status-dot.ok { background: var(--green); }
.status-dot.err { background: var(--red); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; padding: 24px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.card-title { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text2); margin-bottom: 12px; }
.big-number { font-size: 32px; font-weight: 700; }
.big-label { font-size: 13px; color: var(--text2); margin-top: 4px; }
.stat-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 13px; }
.stat-row:last-child { border: none; }
.stat-label { color: var(--text2); }
.stat-value { font-weight: 500; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-green { background: rgba(34,197,94,0.15); color: var(--green); }
.badge-red { background: rgba(239,68,68,0.15); color: var(--red); }
.badge-yellow { background: rgba(234,179,8,0.15); color: var(--yellow); }
.badge-blue { background: rgba(59,130,246,0.15); color: var(--blue); }
.badge-purple { background: rgba(168,85,247,0.15); color: var(--purple); }
.badge-gray { background: rgba(139,143,163,0.15); color: var(--text2); }
.tool-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.tool-item { display: flex; align-items: center; gap: 8px; font-size: 13px; padding: 8px 12px; background: var(--surface2); border-radius: 8px; }
.tool-dot { width: 6px; height: 6px; border-radius: 50%; }
.tool-dot.on { background: var(--green); }
.tool-dot.off { background: var(--red); }
.alert-table { width: 100%; font-size: 12px; border-collapse: collapse; }
.alert-table th { text-align: left; padding: 8px; border-bottom: 1px solid var(--border); color: var(--text2); font-weight: 500; }
.alert-table td { padding: 8px; border-bottom: 1px solid var(--border); }
.alert-table tr:hover { background: var(--surface2); }
.refresh-bar { position: fixed; top: 0; left: 0; height: 2px; background: var(--purple); transition: width 0.3s; z-index: 999; }
.footer { text-align: center; padding: 16px; color: var(--text2); font-size: 12px; }
.section-title { font-size: 16px; font-weight: 600; padding: 8px 24px 0; display: flex; align-items: center; gap: 12px; }
.copy-btn { background: var(--surface2); border: 1px solid var(--border); color: var(--text); padding: 4px 12px; border-radius: 6px; font-size: 11px; cursor: pointer; transition: 0.2s; }
.copy-btn:hover { background: var(--border); }
.copy-btn.copied { background: var(--green); border-color: var(--green); }
.alert-count-badge { font-size: 11px; color: var(--text2); font-weight: 400; }
.score-bar { display: inline-block; width: 60px; height: 4px; background: var(--surface2); border-radius: 2px; overflow: hidden; vertical-align: middle; }
.score-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }
</style>
</head>
<body>
<div class="refresh-bar" id="refreshBar" style="width:0%"></div>

<div class="header">
  <h1>⚡ <span>SVTR</span> Bot Dashboard</h1>
  <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    <button class="copy-btn" id="webhookBtn" onclick="copyWebhookUrl()">Copy Webhook URL</button>
    <span class="status-dot ok" id="statusDot"></span>
    <span id="statusText" style="font-size:13px">Connecting...</span>
    <span style="font-size:11px;color:var(--text2)" id="lastUpdate"></span>
  </div>
</div>

<div class="section-title">System Overview</div>
<div class="grid">
  <div class="card">
    <div class="card-title">Uptime</div>
    <div class="big-number" id="uptime">--</div>
    <div class="big-label" id="uptimeLabel">loading...</div>
  </div>
  <div class="card">
    <div class="card-title">Alerts Processed</div>
    <div class="big-number" id="alertCount" style="color:var(--blue)">0</div>
    <div class="big-label" id="alertRate">webhook alerts</div>
  </div>
  <div class="card">
    <div class="card-title">Last Alert Score</div>
    <div class="big-number" id="lastScore" style="color:var(--purple)">--</div>
    <div class="big-label" id="lastScoreLabel">waiting for signals...</div>
  </div>
  <div class="card">
    <div class="card-title">Fear &amp; Greed</div>
    <div class="big-number" id="fearGreed" style="color:var(--yellow)">--</div>
    <div class="big-label" id="fearGreedLabel">loading...</div>
  </div>
</div>

<div class="section-title">Infrastructure</div>
<div class="grid">
  <div class="card">
    <div class="card-title">Exchange</div>
    <div class="stat-row"><span class="stat-label">Provider</span><span class="stat-value" id="exchId">--</span></div>
    <div class="stat-row"><span class="stat-label">Connected</span><span id="exchConnected">--</span></div>
    <div class="stat-row"><span class="stat-label">Mode</span><span id="exchMode">--</span></div>
  </div>
  <div class="card">
    <div class="card-title">AI Layer</div>
    <div class="stat-row"><span class="stat-label">Status</span><span id="aiStatus">--</span></div>
    <div class="stat-row"><span class="stat-label">Model</span><span class="stat-value" id="aiModel">--</span></div>
    <div class="stat-row"><span class="stat-label">API Calls</span><span class="stat-value" id="aiCalls">0</span></div>
  </div>
  <div class="card">
    <div class="card-title">Strategy</div>
    <div class="stat-row"><span class="stat-label">Symbol</span><span class="stat-value" id="symbol">--</span></div>
    <div class="stat-row"><span class="stat-label">Timeframe</span><span class="stat-value" id="timeframe">--</span></div>
    <div class="stat-row"><span class="stat-label">Min Score</span><span class="stat-value" id="minScore">--</span></div>
    <div class="stat-row"><span class="stat-label">Sentiment</span><span id="sentStatus">--</span></div>
  </div>
  <div class="card">
    <div class="card-title">Social Tools (Agent-Reach)</div>
    <div class="tool-grid">
      <div class="tool-item"><div class="tool-dot" id="twDot"></div><span>Twitter CLI</span></div>
      <div class="tool-item"><div class="tool-dot" id="rdDot"></div><span>Reddit CLI</span></div>
      <div class="tool-item"><div class="tool-dot" id="ytDot"></div><span>yt-dlp</span></div>
      <div class="tool-item"><div class="tool-dot on" style="background:var(--text2)"></div><span>CryptoPanic</span></div>
    </div>
  </div>
</div>

<div class="section-title">
  Recent Alerts
  <span class="alert-count-badge" id="alertCountBadge">(0)</span>
</div>
<div class="grid" style="grid-template-columns:1fr">
  <div class="card" style="overflow-x:auto">
    <table class="alert-table">
      <thead><tr><th>Time</th><th>Symbol</th><th>Direction</th><th>Score</th><th>Action</th><th>AI Conf</th><th>Composite</th></tr></thead>
      <tbody id="alertBody"><tr><td colspan="7" style="text-align:center;color:var(--text2)">No alerts yet — waiting for TradingView webhooks...</td></tr></tbody>
    </table>
  </div>
</div>

<div class="section-title">Prometheus Metrics</div>
<div class="grid" style="grid-template-columns:1fr">
  <div class="card"><pre id="metricsPre" style="font-size:11px;color:var(--text2);white-space:pre-wrap;max-height:200px;overflow-y:auto">Loading metrics...</pre></div>
</div>

<div class="footer">SVTR Bot v1.0.0 — Smart VWAP Trend Rider — Auto-refreshes every 5s</div>

<script>
let prevCount = 0;

async function fetchStatus() {
  try {
    const r = await fetch('/status');
    const d = await r.json();
    document.getElementById('statusDot').className = 'status-dot ok';
    document.getElementById('statusText').textContent = 'Connected';
    document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
    document.getElementById('uptime').textContent = fmtUptime(d.runtime.uptime_seconds);
    document.getElementById('uptimeLabel').textContent = 'since ' + new Date(Date.now() - d.runtime.uptime_seconds*1000).toLocaleTimeString();
    document.getElementById('alertCount').textContent = d.runtime.alerts_processed;
    document.getElementById('exchId').textContent = d.exchange.id;
    document.getElementById('exchConnected').innerHTML = d.exchange.connected ? '<span class="badge badge-green">Connected</span>' : '<span class="badge badge-red">Disconnected</span>';
    document.getElementById('exchMode').innerHTML = d.exchange.testnet ? '<span class="badge badge-yellow">Testnet</span>' : '<span class="badge badge-green">Mainnet</span>';
    document.getElementById('aiStatus').innerHTML = d.ai.enabled ? '<span class="badge badge-green">Enabled</span>' : '<span class="badge badge-gray">Disabled</span>';
    document.getElementById('aiModel').textContent = d.ai.model || 'N/A';
    document.getElementById('symbol').textContent = d.strategy.symbol;
    document.getElementById('timeframe').textContent = d.strategy.timeframe;
    document.getElementById('minScore').textContent = d.strategy.min_score;
    document.getElementById('sentStatus').innerHTML = d.strategy.sentiment_enabled ? '<span class="badge badge-green">ON</span>' : '<span class="badge badge-gray">OFF</span>';
    setDot('twDot', d.social_tools.twitter_cli);
    setDot('rdDot', d.social_tools.rdt_cli);
    setDot('ytDot', d.social_tools.yt_dlp);
  } catch(e) {
    document.getElementById('statusDot').className = 'status-dot err';
    document.getElementById('statusText').textContent = 'Disconnected';
  }
}

async function fetchAlerts() {
  try {
    const r = await fetch('/api/alerts');
    const alerts = await r.json();
    document.getElementById('alertCountBadge').textContent = '(' + alerts.length + ')';
    const tbody = document.getElementById('alertBody');
    if (alerts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text2)">No alerts yet</td></tr>';
      return;
    }
    const rows = alerts.slice().reverse().slice(0, 20).map(a => {
      const dir = a.direction || '';
      const dirBadge = dir === 'long' ? 'badge-green' : dir === 'short' ? 'badge-red' : 'badge-gray';
      const scorePct = Math.min(100, (a.score || 0) / 13.5 * 100);
      return '<tr>' +
        '<td>' + (a.time ? a.time.slice(11, 19) : '--') + '</td>' +
        '<td><b>' + (a.symbol || '--') + '</b></td>' +
        '<td><span class="badge ' + dirBadge + '">' + dir + '</span></td>' +
        '<td>' + a.score + ' <div class="score-bar"><div class="score-fill" style="width:' + scorePct + '%;background:' + (scorePct > 60 ? 'var(--green)' : scorePct > 40 ? 'var(--yellow)' : 'var(--red)') + '"></div></div></td>' +
        '<td>' + (a.action || '--') + '</td>' +
        '<td>' + (a.ai_confidence || '--') + '</td>' +
        '<td>' + (a.composite || '--') + '</td>' +
        '</tr>';
    }).join('');
    tbody.innerHTML = rows;
    // Update last score
    const last = alerts[alerts.length - 1];
    if (last && last.score) {
      document.getElementById('lastScore').textContent = last.score;
      document.getElementById('lastScoreLabel').textContent = 'from ' + (last.symbol || '') + ' ' + (last.direction || '');
    }
  } catch(e) { console.log('Alerts fetch error:', e); }
}

function setDot(id, on) {
  document.getElementById(id).className = 'tool-dot ' + (on ? 'on' : 'off');
}

function fmtUptime(s) {
  if (s < 60) return Math.floor(s) + 's';
  if (s < 3600) return Math.floor(s/60) + 'm ' + Math.floor(s%60) + 's';
  return Math.floor(s/3600) + 'h ' + Math.floor((s%3600)/60) + 'm';
}

async function fetchMetrics() {
  try {
    const r = await fetch('/metrics');
    document.getElementById('metricsPre').textContent = await r.text();
  } catch(e) {}
}

function copyWebhookUrl() {
  const url = window.location.origin + '/webhook';
  navigator.clipboard.writeText(url).then(() => {
    const btn = document.getElementById('webhookBtn');
    btn.textContent = 'Copied URL!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy Webhook URL'; btn.classList.remove('copied'); }, 2000);
  });
}

async function refresh() {
  const bar = document.getElementById('refreshBar');
  bar.style.width = '100%';
  await Promise.all([fetchStatus(), fetchAlerts(), fetchMetrics()]);
  setTimeout(() => { bar.style.width = '0%'; }, 300);
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""
