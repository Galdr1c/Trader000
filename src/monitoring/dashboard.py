"""Live HTML Dashboard — real-time monitoring for SVTR Bot.

Serves a beautiful, auto-refreshing dashboard at GET /
that displays: bot status, alerts, news feed, social media stream,
sentiment gauges, Agent-Reach status, and Prometheus metrics.
"""

from __future__ import annotations

DASHBOARD_HTML = r"""<!DOCTYPE html>
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
  --purple: #a855f7; --cyan: #06b6d4; --orange: #f97316; --pink: #ec4899;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', -apple-system, system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }
.header { background: linear-gradient(135deg, #1a1d27 0%, #0f1117 100%); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; position: sticky; top: 0; z-index: 100; }
.header h1 { font-size: 20px; font-weight: 600; }
.header h1 span { color: var(--purple); }
.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 8px; animation: pulse 2s infinite; }
.status-dot.ok { background: var(--green); }
.status-dot.err { background: var(--red); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; padding: 16px 24px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px 20px; }
.card-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text2); margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
.big-number { font-size: 32px; font-weight: 700; }
.big-label { font-size: 12px; color: var(--text2); margin-top: 2px; }
.stat-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 13px; }
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
.badge-orange { background: rgba(249,115,22,0.15); color: var(--orange); }
.tool-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.tool-item { display: flex; align-items: center; gap: 8px; font-size: 12px; padding: 6px 10px; background: var(--surface2); border-radius: 8px; }
.tool-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.tool-dot.on { background: var(--green); box-shadow: 0 0 6px var(--green); }
.tool-dot.off { background: var(--red); }
.alert-table { width: 100%; font-size: 12px; border-collapse: collapse; }
.alert-table th { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); color: var(--text2); font-weight: 500; font-size: 11px; }
.alert-table td { padding: 6px 8px; border-bottom: 1px solid var(--border); }
.alert-table tr:hover { background: var(--surface2); }
.refresh-bar { position: fixed; top: 0; left: 0; height: 2px; background: var(--purple); transition: width 0.3s; z-index: 999; }
.footer { text-align: center; padding: 16px; color: var(--text2); font-size: 11px; }
.section-title { font-size: 15px; font-weight: 600; padding: 16px 24px 0; display: flex; align-items: center; gap: 12px; }
.copy-btn { background: var(--surface2); border: 1px solid var(--border); color: var(--text); padding: 4px 12px; border-radius: 6px; font-size: 11px; cursor: pointer; transition: 0.2s; }
.copy-btn:hover { background: var(--border); }
.score-bar { display: inline-block; width: 60px; height: 4px; background: var(--surface2); border-radius: 2px; overflow: hidden; vertical-align: middle; }
.score-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }

/* News cards */
.news-feed { display: flex; flex-direction: column; gap: 6px; max-height: 400px; overflow-y: auto; }
.news-card { display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; background: var(--surface2); border-radius: 8px; border-left: 3px solid var(--border); font-size: 13px; transition: 0.2s; }
.news-card:hover { border-color: var(--purple); }
.news-sent { font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 3px; white-space: nowrap; }
.news-sent.bullish { background: rgba(34,197,94,0.15); color: var(--green); }
.news-sent.bearish { background: rgba(239,68,68,0.15); color: var(--red); }
.news-sent.neutral { background: rgba(139,143,163,0.15); color: var(--text2); }
.news-sent.important { background: rgba(168,85,247,0.15); color: var(--purple); }
.news-title { flex: 1; color: var(--text); }
.news-time { font-size: 10px; color: var(--text2); white-space: nowrap; }

/* Social feed */
.social-feed { display: flex; flex-direction: column; gap: 6px; max-height: 300px; overflow-y: auto; }
.social-item { display: flex; align-items: flex-start; gap: 10px; padding: 8px 12px; background: var(--surface2); border-radius: 8px; font-size: 12px; }
.social-icon { font-size: 14px; flex-shrink: 0; }
.social-text { flex: 1; color: var(--text); }

/* Sentiment gauge */
.gauge-container { text-align: center; padding: 8px 0; }
.gauge { width: 140px; height: 70px; position: relative; margin: 0 auto; overflow: hidden; }
.gauge-bg { width: 140px; height: 140px; background: conic-gradient(var(--red) 0deg, var(--yellow) 90deg, var(--green) 180deg); border-radius: 50%; position: absolute; top: 0; }
.gauge-cover { width: 100px; height: 100px; background: var(--surface); border-radius: 50%; position: absolute; top: 20px; left: 20px; display: flex; align-items: center; justify-content: center; flex-direction: column; }
.gauge-value { font-size: 24px; font-weight: 700; }
.gauge-label { font-size: 10px; color: var(--text2); text-transform: uppercase; }
.gauge-needle { width: 2px; height: 60px; background: var(--text); position: absolute; bottom: 10px; left: 50%; transform-origin: bottom center; transition: transform 0.5s; border-radius: 2px; }
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

<!-- System Overview -->
<div class="section-title">System Overview</div>
<div class="grid">
  <div class="card">
    <div class="card-title">Uptime</div>
    <div class="big-number" id="uptime">--</div>
    <div class="big-label" id="uptimeLabel">loading...</div>
  </div>
  <div class="card">
    <div class="card-title">Alerts</div>
    <div class="big-number" id="alertCount" style="color:var(--blue)">0</div>
    <div class="big-label">webhook signals received</div>
  </div>
  <div class="card">
    <div class="card-title">Fear &amp; Greed</div>
    <div class="gauge-container">
      <div class="gauge">
        <div class="gauge-bg"></div>
        <div class="gauge-needle" id="fgNeedle" style="transform:rotate(0deg)"></div>
        <div class="gauge-cover">
          <span class="gauge-value" id="fgValue">--</span>
          <span class="gauge-label" id="fgLabel">neutral</span>
        </div>
      </div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Signal Score</div>
    <div class="big-number" id="lastScore" style="color:var(--purple)">--</div>
    <div class="big-label" id="lastScoreLabel">waiting for signals...</div>
  </div>
</div>

<!-- Infrastructure -->
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
    <div class="stat-row"><span class="stat-label">TradingAgents</span><span id="taStatus">--</span></div>
  </div>
  <div class="card">
    <div class="card-title">Strategy</div>
    <div class="stat-row"><span class="stat-label">Symbol</span><span class="stat-value" id="symbol">--</span></div>
    <div class="stat-row"><span class="stat-label">Timeframe</span><span class="stat-value" id="timeframe">--</span></div>
    <div class="stat-row"><span class="stat-label">Min Score</span><span class="stat-value" id="minScore">--</span></div>
    <div class="stat-row"><span class="stat-label">Sentiment</span><span id="sentStatus">--</span></div>
  </div>
  <div class="card">
    <div class="card-title">Agent-Reach / Social Tools</div>
    <div class="tool-grid">
      <div class="tool-item"><div class="tool-dot" id="twDot"></div><span>Twitter CLI</span><span style="margin-left:auto;font-size:10px;color:var(--text2)" id="twStatus">idle</span></div>
      <div class="tool-item"><div class="tool-dot" id="rdDot"></div><span>Reddit CLI</span><span style="margin-left:auto;font-size:10px;color:var(--text2)" id="rdStatus">idle</span></div>
      <div class="tool-item"><div class="tool-dot" id="ytDot"></div><span>yt-dlp</span><span style="margin-left:auto;font-size:10px;color:var(--text2)" id="ytStatus">idle</span></div>
      <div class="tool-item"><div class="tool-dot" id="cpDot"></div><span>CryptoPanic</span><span style="margin-left:auto;font-size:10px;color:var(--text2)" id="cpStatus">idle</span></div>
    </div>
  </div>
</div>

<!-- Recent Alerts -->
<div class="section-title">Recent Alerts <span class="badge badge-blue" id="alertCountBadge">0</span></div>
<div class="grid" style="grid-template-columns:1fr">
  <div class="card" style="overflow-x:auto">
    <table class="alert-table">
      <thead><tr><th>Time</th><th>Symbol</th><th>Direction</th><th>Score</th><th>Action</th><th>AI Conf</th><th>Composite</th></tr></thead>
      <tbody id="alertBody"><tr><td colspan="7" style="text-align:center;color:var(--text2)">No alerts yet — waiting for signals...</td></tr></tbody>
    </table>
  </div>
</div>

<!-- Portfolio -->
<div class="section-title">Portfolio</div>
<div class="grid">
  <div class="card">
    <div class="card-title">Open Positions</div>
    <div class="big-number" id="openPositionCount">0</div>
    <div class="big-label">active symbols</div>
  </div>
  <div class="card">
    <div class="card-title">Unrealized P&amp;L</div>
    <div class="big-number" id="unrealizedPnl">0.00</div>
    <div class="big-label">current scanner prices</div>
  </div>
  <div class="card">
    <div class="card-title">Realized P&amp;L</div>
    <div class="big-number" id="realizedPnl">0.00</div>
    <div class="big-label">closed positions</div>
  </div>
</div>
<div class="grid" style="grid-template-columns:2fr 1fr">
  <div class="card" style="overflow-x:auto">
    <table class="alert-table">
      <thead><tr><th>Symbol</th><th>Side</th><th>Entry</th><th>Current</th><th>Qty</th><th>P&amp;L</th></tr></thead>
      <tbody id="positionBody"><tr><td colspan="6" style="text-align:center;color:var(--text2)">No open positions</td></tr></tbody>
    </table>
  </div>
  <div class="card">
    <div class="card-title">Cumulative Realized P&amp;L</div>
    <canvas id="pnlChart" width="420" height="180" style="width:100%;height:180px"></canvas>
  </div>
</div>

<!-- News Feed -->
<div class="section-title">News Feed <span id="newsCount" class="badge badge-gray">0</span></div>
<div class="grid" style="grid-template-columns:1fr">
  <div class="card">
    <div class="news-feed" id="newsFeed">
      <div style="text-align:center;color:var(--text2);padding:20px">Loading news...</div>
    </div>
  </div>
</div>

<!-- Social Media Stream -->
<div class="section-title">Social Media Stream <span id="socialCount" class="badge badge-gray">0</span></div>
<div class="grid" style="grid-template-columns:1fr">
  <div class="card">
    <div class="social-feed" id="socialFeed">
      <div style="text-align:center;color:var(--text2);padding:20px">Social tools idle — install Agent-Reach CLI</div>
    </div>
  </div>
</div>

<!-- Metrics -->
<div class="section-title">Prometheus Metrics</div>
<div class="grid" style="grid-template-columns:1fr">
  <div class="card"><pre id="metricsPre" style="font-size:11px;color:var(--text2);white-space:pre-wrap;max-height:150px;overflow-y:auto">Loading...</pre></div>
</div>

<div class="footer">SVTR Bot v1.0.0 — Smart VWAP Trend Rider — Refreshes every 10s</div>

<script>
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
    document.getElementById('twStatus').textContent = d.social_tools.twitter_cli ? 'ready' : 'missing';
    document.getElementById('rdStatus').textContent = d.social_tools.rdt_cli ? 'ready' : 'missing';
    document.getElementById('ytStatus').textContent = d.social_tools.yt_dlp ? 'ready' : 'missing';
  } catch(e) {
    document.getElementById('statusDot').className = 'status-dot err';
    document.getElementById('statusText').textContent = 'Disconnected';
  }
}

async function fetchAlerts() {
  try {
    const r = await fetch('/api/alerts');
    const alerts = await r.json();
    document.getElementById('alertCountBadge').textContent = alerts.length;
    const tbody = document.getElementById('alertBody');
    if (alerts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text2)">No alerts yet</td></tr>';
      return;
    }
    tbody.innerHTML = alerts.slice().reverse().slice(0, 20).map(a => {
      const scorePct = Math.min(100, (a.score || 0) / 13.5 * 100);
      return '<tr><td>'+(a.time?a.time.slice(11,19):'--')+'</td><td><b>'+(a.symbol||'--')+'</b></td><td><span class="badge '+(a.direction==='long'?'badge-green':a.direction==='short'?'badge-red':'badge-gray')+'">'+(a.direction||'')+'</span></td><td>'+a.score+' <div class="score-bar"><div class="score-fill" style="width:'+scorePct+'%;background:'+(scorePct>60?'var(--green)':scorePct>40?'var(--yellow)':'var(--red)')+'"></div></div></td><td>'+(a.action||'--')+'</td><td>'+(a.ai_confidence||'--')+'</td><td>'+(a.composite||'--')+'</td></tr>';
    }).join('');
    const last = alerts[alerts.length-1];
    if(last && last.score) { document.getElementById('lastScore').textContent = last.score; document.getElementById('lastScoreLabel').textContent = 'from '+(last.symbol||'')+' '+(last.direction||''); }
  } catch(e) {}
}

async function fetchPortfolio() {
  try {
    const [positionsResponse, performanceResponse] = await Promise.all([
      fetch('/api/positions'),
      fetch('/api/performance')
    ]);
    const positionsData = await positionsResponse.json();
    const performanceData = await performanceResponse.json();
    const summary = positionsData.summary || {};
    document.getElementById('openPositionCount').textContent = summary.active_count || 0;
    setPnlValue('unrealizedPnl', summary.unrealized_value || 0);
    setPnlValue('realizedPnl', summary.realized_value || 0);

    const body = document.getElementById('positionBody');
    body.replaceChildren();
    const positions = positionsData.positions || [];
    if (positions.length === 0) {
      const row = body.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 6;
      cell.style.textAlign = 'center';
      cell.style.color = 'var(--text2)';
      cell.textContent = 'No open positions';
    } else {
      positions.forEach(position => {
        const row = body.insertRow();
        const values = [
          position.symbol,
          position.side,
          fmtNumber(position.entry_price),
          position.current_price == null ? 'unavailable' : fmtNumber(position.current_price),
          fmtNumber(position.quantity),
          position.unrealized_pnl == null ? 'unavailable' : fmtNumber(position.unrealized_pnl)
        ];
        values.forEach(value => {
          const cell = row.insertCell();
          cell.textContent = value;
        });
      });
    }
    drawPnlChart(performanceData.series || []);
  } catch(e) {}
}

function fmtNumber(value) {
  return Number(value || 0).toFixed(2);
}

function setPnlValue(id, value) {
  const element = document.getElementById(id);
  element.textContent = fmtNumber(value);
  element.style.color = value > 0 ? 'var(--green)' : value < 0 ? 'var(--red)' : 'var(--text)';
}

function drawPnlChart(series) {
  const canvas = document.getElementById('pnlChart');
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (series.length < 2) return;
  const values = series.map(point => Number(point.pnl || 0));
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const span = Math.max(1, max - min);
  ctx.strokeStyle = values[values.length - 1] >= 0 ? '#22c55e' : '#ef4444';
  ctx.lineWidth = 3;
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = 10 + index * (canvas.width - 20) / Math.max(1, values.length - 1);
    const y = canvas.height - 10 - (value - min) * (canvas.height - 20) / span;
    if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

async function fetchFeed() {
  try {
    const r = await fetch('/api/feed');
    const d = await r.json();
    
    // Fear & Greed gauge
    const fg = d.fear_greed || 50;
    const fgDeg = (fg / 100) * 180;
    document.getElementById('fgValue').textContent = fg;
    document.getElementById('fgNeedle').style.transform = 'rotate(' + fgDeg + 'deg)';
    const fgLabel = fg > 75 ? 'Extreme Greed' : fg > 55 ? 'Greed' : fg > 45 ? 'Neutral' : fg > 25 ? 'Fear' : 'Extreme Fear';
    document.getElementById('fgLabel').textContent = fgLabel;
    document.getElementById('fgValue').style.color = fg > 55 ? 'var(--green)' : fg < 45 ? 'var(--red)' : 'var(--yellow)';

    // CryptoPanic status
    setDot('cpDot', true);
    document.getElementById('cpStatus').textContent = d.news.length > 0 ? d.news.length + ' articles' : 'no data';

    // News feed
    const news = d.news || [];
    document.getElementById('newsCount').textContent = news.length;
    const newsHtml = news.map(n => {
      const sent = n.sentiment_label || 'neutral';
      const sentClass = sent === 'bullish' ? 'bullish' : sent === 'bearish' ? 'bearish' : sent === 'important' ? 'important' : 'neutral';
      return '<div class="news-card"><span class="news-sent ' + sentClass + '">' + sent + '</span><span class="news-title">' + (n.title || '') + '</span><span class="news-time">' + (n.published ? n.published.slice(11,16) : '') + '</span></div>';
    }).join('');
    document.getElementById('newsFeed').innerHTML = newsHtml || '<div style="text-align:center;color:var(--text2);padding:20px">No news found</div>';

    // Social tools status
    const tools = d.social_tools || {};
    setDot('twDot', tools.twitter_cli);
    setDot('rdDot', tools.rdt_cli);
    setDot('ytDot', tools.yt_dlp);
    document.getElementById('twStatus').textContent = tools.twitter_cli ? 'ready' : 'install agent-reach';
    document.getElementById('rdStatus').textContent = tools.rdt_cli ? 'ready' : 'install agent-reach';
    document.getElementById('ytStatus').textContent = tools.yt_dlp ? 'ready' : 'missing';

    // Social feed status
    const socialFeed = document.getElementById('socialFeed');
    const available = tools.twitter_cli || tools.rdt_cli;
    socialFeed.innerHTML = available
      ? '<div style="text-align:center;color:var(--green);padding:20px">Social CLI tools available — install Agent-Reach to enable live streaming</div>'
      : '<div style="text-align:center;color:var(--text2);padding:20px">Install Agent-Reach CLI for live Twitter + Reddit streaming:<br><code style="font-size:11px;background:var(--surface2);padding:4px 8px;border-radius:4px;margin-top:8px;display:inline-block">pipx install agent-reach && agent-reach install</code></div>';

  } catch(e) { console.log('Feed fetch error:', e); }
}

function setDot(id, on) { const el = document.getElementById(id); if(el) el.className = 'tool-dot ' + (on ? 'on' : 'off'); }

function fmtUptime(s) {
  if (s < 60) return Math.floor(s) + 's';
  if (s < 3600) return Math.floor(s/60) + 'm ' + Math.floor(s%60) + 's';
  return Math.floor(s/3600) + 'h ' + Math.floor((s%3600)/60) + 'm';
}

async function fetchMetrics() {
  try { const r = await fetch('/metrics'); document.getElementById('metricsPre').textContent = await r.text(); } catch(e) {}
}

function copyWebhookUrl() {
  navigator.clipboard.writeText(window.location.origin + '/webhook').then(() => {
    const btn = document.getElementById('webhookBtn');
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy Webhook URL'; }, 2000);
  });
}

async function refresh() {
  const bar = document.getElementById('refreshBar');
  bar.style.width = '100%';
  await Promise.all([fetchStatus(), fetchAlerts(), fetchPortfolio(), fetchFeed(), fetchMetrics()]);
  setTimeout(() => { bar.style.width = '0%'; }, 300);
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""
