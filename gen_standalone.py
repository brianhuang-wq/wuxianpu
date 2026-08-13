#!/usr/bin/env python3
"""產生「免安裝、可雙擊開啟」的樂活五線譜獨立 HTML。

價格資料在產生時嵌入檔案，迴歸運算改由瀏覽器端執行，
因此使用者可以任意輸入回歸年限、即時重算，完全不需要 Python 或網路。
"""
import argparse
import datetime as dt
import json
import os

import wuxianpu as core

TICKERS = [("0050", "元大台灣50"), ("0056", "元大高股息"), ("006208", "富邦台50"),
           ("2330", "台積電"), ("2454", "聯發科"), ("009816", "凱基台灣50"),
           ("^TWII", "台股加權指數")]

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>樂活五線譜</title>
<meta name="description" content="股價位階分析：線性迴歸趨勢線與 ±1σ、±2σ 五線譜，含月線至十年線比較。">
<meta name="theme-color" content="#1a202c">
<link rel="manifest" href="manifest.json">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="icon" type="image/png" href="icon-192.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="五線譜">
<style>
  :root { --bg:#f6f7f9; --panel:#fff; --fg:#1a1a1a; --muted:#6b7280; --line:#e5e7eb;
          --accent:#1a1a1a; --hl:#fff3c4; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#101115; --panel:#1b1d23; --fg:#e9e9ee; --muted:#9aa0ac; --line:#2c2f37;
            --accent:#e9e9ee; --hl:#3d3a1f; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font-size:14px;
         font-family:-apple-system,"PingFang TC","Noto Sans TC","Microsoft JhengHei",sans-serif; }
  .top { background:var(--panel); border-bottom:1px solid var(--line); padding:16px 22px; }
  .inner { max-width:1240px; margin:0 auto; }
  h1 { font-size:17px; margin:0 0 3px; font-weight:600; }
  .tagline { font-size:12px; color:var(--muted); margin-bottom:15px; }
  .row { display:flex; gap:22px; flex-wrap:wrap; align-items:flex-end; }
  .fld { display:flex; flex-direction:column; gap:6px; }
  label { font-size:12px; color:var(--muted); font-weight:500; }
  select, input[type=text] { background:var(--bg); border:1px solid var(--line); color:var(--fg);
    border-radius:8px; padding:9px 11px; font-size:14px; font-family:inherit; }
  select { min-width:190px; font-weight:600; }
  #custom { width:180px; }
  #code { width:150px; }
  input[type=text] { background:var(--bg); border:1px solid var(--line); color:var(--fg);
    border-radius:8px; padding:9px 11px; font-size:14px; font-family:inherit; }
  .status { font-size:12.5px; margin-top:10px; padding:8px 12px; border-radius:8px; display:none; }
  .status.on { display:block; }
  .status.err { background:#fee2e2; color:#991b1b; }
  .status.ok  { background:#e0f2fe; color:#075985; }
  @media (prefers-color-scheme: dark) {
    .status.err { background:#3b1616; color:#fca5a5; }
    .status.ok  { background:#0c2b3d; color:#7dd3fc; }
  }
  .chips { display:flex; gap:7px; flex-wrap:wrap; }
  .chip input { display:none; }
  .chip span { display:block; border:1px solid var(--line); background:var(--bg); border-radius:8px;
     padding:9px 15px; cursor:pointer; user-select:none; font-size:13.5px; }
  .chip input:checked + span { background:var(--accent); color:var(--bg);
     border-color:var(--accent); font-weight:600; }
  button { background:var(--accent); color:var(--bg); border:0; border-radius:8px; padding:10px 26px;
     font-size:14px; font-weight:600; cursor:pointer; font-family:inherit; }
  button:active { opacity:.75; }
  .body { max-width:1240px; margin:0 auto; padding:20px 22px 40px; }
  .stats { display:flex; gap:34px; flex-wrap:wrap; margin-bottom:14px; }
  .stat .k { font-size:12px; color:var(--muted); margin-bottom:3px; }
  .stat .v { font-size:22px; font-weight:600; }
  .tabs { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px; }
  .tabs button { background:var(--panel); color:var(--muted); border:1px solid var(--line);
     padding:7px 16px; font-size:13.5px; font-weight:500; }
  .tabs button.on { background:var(--accent); color:var(--bg); border-color:var(--accent); font-weight:600; }
  .warn { background:#fef3c7; color:#92400e; border-radius:8px; padding:10px 14px;
          font-size:13px; margin-bottom:14px; }
  @media (prefers-color-scheme: dark) { .warn { background:#3a2f12; color:#fcd34d; } }
  #chart { position:relative; width:100%; background:var(--panel); border:1px solid var(--line);
           border-radius:12px; padding:12px 10px 6px; }
  svg { display:block; width:100%; overflow:visible; }
  #tip { position:absolute; pointer-events:none; opacity:0; transition:opacity .1s;
     background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:9px 11px;
     font-size:12.5px; line-height:1.65; box-shadow:0 6px 20px rgba(0,0,0,.16);
     white-space:nowrap; z-index:5; }
  #tip .d { font-weight:600; margin-bottom:4px; }
  #tip .r { display:flex; align-items:center; gap:7px; }
  #tip .dot { width:9px; height:9px; border-radius:50%; flex:none; }
  #tip .nm { flex:1; } #tip .vl { font-variant-numeric:tabular-nums; font-weight:600; }
  .legend { display:flex; gap:16px; flex-wrap:wrap; margin-top:12px; font-size:12.5px; color:var(--muted); }
  .legend span { display:flex; align-items:center; gap:6px; }
  .legend i { width:14px; height:3px; border-radius:2px; display:block; }
  table { border-collapse:collapse; width:100%; margin-top:26px; font-size:13px; }
  th,td { padding:8px 10px; text-align:right; border-bottom:1px solid var(--line); }
  th:first-child, td:first-child { text-align:left; }
  th { color:var(--muted); font-weight:500; }
  td { font-variant-numeric:tabular-nums; }
  .cap { font-size:13px; color:var(--muted); margin:26px 0 -18px; font-weight:600; }
  .note { font-size:12.5px; color:var(--muted); margin-top:22px; line-height:1.8; }
  .updated { font-size:12px; color:var(--muted); margin-top:18px; }

  /* 行動裝置：縮排、欄位改為整列、表格字級縮小 */
  @media (max-width: 640px) {
    body { font-size:13.5px; }
    .top { padding:13px 14px; }
    .body { padding:16px 14px 34px; }
    h1 { font-size:16px; }
    .row { gap:14px; }
    .fld { flex:1 1 100%; }
    select, #custom { width:100%; min-width:0; }
    button { width:100%; padding:12px; }
    .chips { width:100%; }
    .chip span { padding:9px 0; flex:1; text-align:center; }
    .chip { flex:1; }
    .stats { gap:18px; }
    .stat .v { font-size:19px; }
    th, td { padding:7px 5px; font-size:12px; }
    .cap { margin:22px 0 -14px; }
    #chart { padding:8px 4px 4px; }
  }
</style>
</head>
<body>
<div class="top"><div class="inner">
  <h1>樂活五線譜　股價位階分析</h1>
  <div class="tagline">內建資料截至 __ASOF__（僅含已收盤價格）　·　所有運算在本機瀏覽器完成　·　
  自行輸入台股代碼可即時查詢</div>
  <div class="row">
    <div class="fld">
      <label for="tk">股票（內建清單）</label>
      <select id="tk" onchange="pickPreset()"></select>
    </div>
    <div class="fld">
      <label for="code">或自行輸入台股代碼</label>
      <div style="display:flex;gap:7px">
        <input type="text" id="code" placeholder="例：2412、00878"
               autocomplete="off" inputmode="numeric"
               onkeydown="if(event.key==='Enter')fetchCode()">
        <button type="button" onclick="fetchCode()" style="padding:9px 16px">查詢</button>
      </div>
    </div>
    <div class="fld">
      <label>回歸年限（可複選）</label>
      <div class="chips" id="chips"></div>
    </div>
    <div class="fld">
      <label for="custom">自行輸入年限</label>
      <input type="text" id="custom" placeholder="例：0.5 2 7.5"
             onkeydown="if(event.key==='Enter')go()">
    </div>
    <button onclick="go()">分析</button>
  </div>
  <div class="status" id="msg"></div>
</div></div>

<div class="body">
  <div class="stats">
    <div class="stat"><div class="k">標的</div><div class="v" id="name" style="font-size:17px;padding-top:4px"></div></div>
    <div class="stat"><div class="k">最新收盤</div><div class="v" id="px"></div></div>
    <div class="stat"><div class="k">市場情緒</div><div class="v" id="mood"></div></div>
    <div class="stat"><div class="k">標準差 σ</div><div class="v" id="sig"></div></div>
    <div class="stat"><div class="k">回歸區間</div><div class="v" id="rng" style="font-size:15px;padding-top:5px"></div></div>
  </div>
  <div class="tabs" id="tabs"></div>
  <div id="warnbox"></div>
  <div id="chart"><div id="tip"></div></div>
  <div class="legend" id="legend"></div>
  <div id="tbl"></div>
  <div id="ovw"></div>
  <div class="updated">資料更新時間：__ASOF__（每個交易日收盤後自動更新）</div>
  <div class="note">
    <b>演算法</b>：取區間內日收盤價（未還原權息），以交易日序號為 x 跑最小平方線性迴歸得趨勢線，
    再以殘差標準差 σ 畫出 ±1σ、±2σ 共五條線。已對照 sentimentinsideout.com 驗證，誤差 &lt; 0.15。<br>
    <b>提醒</b>：新上市標的（如 009816）歷史不足時，長年限的五條線統計意義有限，畫面上會出現警告。<br>
    <b>自行輸入代碼</b>：即時向 FinMind 查詢，僅支援台股（上市／上櫃）。
    內建清單則為預先嵌入的資料，開啟即可用、不需連網。<br>
    本工具僅為技術面數值計算，<b>不構成投資建議</b>。
  </div>
</div>

<script>
const DATA = __DATA__;
const BANDS = [["極度貪婪",2,"#d81b60"],["貪婪",1,"#f48fb1"],["趨勢線",0,"#546e7a"],
               ["恐懼",-1,"#4fc3f7"],["極度恐懼",-2,"#1565c0"]];
const MOODC = {"極度貪婪":"#d81b60","貪婪":"#ec7fa4","中性":"#546e7a",
               "恐懼":"#4fc3f7","極度恐懼":"#1565c0"};
const PRESET = [1, 3.5, 5, 10];
const MAS = [["月線",20],["季線",60],["半年線",120],["年線",240],
             ["兩年線",480],["五年線",1200],["十年線",2400]];
const MACOLOR = "#8b7355";
let PAD = { t:14, r:62, b:30, l:56 };
function tunePad() {
  const narrow = window.innerWidth < 640;
  PAD = narrow ? { t:10, r:46, b:26, l:42 } : { t:14, r:62, b:30, l:56 };
}
tunePad();

let periods = [], cur = null, geom = null;
const chart = document.getElementById('chart'), tip = document.getElementById('tip');

document.getElementById('tk').innerHTML =
  DATA.map((d,i) => `<option value="${i}">${d.code}　${d.label}</option>`).join('');
document.getElementById('chips').innerHTML =
  PRESET.map(y => `<label class="chip"><input type="checkbox" value="${y}"
    ${[1,3.5,5,10].includes(y)?'checked':''}><span>${y} 年</span></label>`).join('');

function num2date(n) { return new Date(Math.floor(n/10000), Math.floor(n/100)%100-1, n%100); }
function fmtDate(n) { const s=String(n); return `${s.slice(0,4)}/${s.slice(4,6)}/${s.slice(6)}`; }

// 對指定年限切窗、跑最小平方迴歸
function compute(d, years) {
  const endN = d.dates[d.dates.length-1];
  const startMs = num2date(endN).getTime() - years*365.25*86400000;
  let s = 0;
  while (s < d.dates.length && num2date(d.dates[s]).getTime() < startMs) s++;
  const dates = d.dates.slice(s), y = d.closes.slice(s), m = y.length;
  if (m < 3) return null;

  let sx=0, sy=0, sxy=0, sxx=0;
  for (let i=0; i<m; i++) { sx+=i; sy+=y[i]; sxy+=i*y[i]; sxx+=i*i; }
  const slope = (m*sxy - sx*sy) / (m*sxx - sx*sx);
  const icpt = (sy - slope*sx) / m;
  let ss = 0;
  for (let i=0; i<m; i++) { const r = y[i]-(icpt+slope*i); ss += r*r; }
  const sigma = Math.sqrt(ss/m);
  const t0 = icpt, tN = icpt + slope*(m-1), price = y[m-1];

  const levels = {}; BANDS.forEach(b => levels[b[0]] = tN + b[1]*sigma);
  let mood = "中性";
  if (price > levels["極度貪婪"]) mood = "極度貪婪";
  else if (price > levels["貪婪"]) mood = "貪婪";
  else if (price < levels["極度恐懼"]) mood = "極度恐懼";
  else if (price < levels["恐懼"]) mood = "恐懼";

  const actual = (num2date(dates[m-1]) - num2date(dates[0])) / (365.25*86400000);
  let warn = "";
  if (actual < years*0.9)
    warn = `要求 ${years} 年，實際僅取得 ${actual.toFixed(2)} 年（${m} 個交易日）。`
         + `多為新上市標的所致，五條線僅供參考，統計意義有限。`;
  else if (m < 60) warn = `樣本僅 ${m} 個交易日，迴歸結果不穩定。`;

  const pos = (price - levels["極度恐懼"]) / (levels["極度貪婪"] - levels["極度恐懼"]) * 100;
  return { years, dates, prices:y, n:m, t0, tN, sigma, levels, mood, price, warn, pos,
           range: `${fmtDate(dates[0])} ~ ${fmtDate(dates[m-1])}` };
}

function movingAverages(closes) {
  return MAS.map(([nm, n]) => {
    if (closes.length < n) return { nm, n, ok:false, have:closes.length };
    let s = 0;
    for (let i = closes.length - n; i < closes.length; i++) s += closes[i];
    return { nm, n, ok:true, v:s/n };
  });
}

function lineVal(p, k, i) { return p.t0 + (p.tN-p.t0)*(p.n>1 ? i/(p.n-1) : 0) + k*p.sigma; }

function render() {
  tunePad();
  const narrow = window.innerWidth < 640;
  const p = cur, W = chart.clientWidth - (narrow ? 8 : 20);
  const H = narrow ? Math.max(300, W * 0.95) : Math.max(360, Math.min(540, W * 0.5));
  const iw = W-PAD.l-PAD.r, ih = H-PAD.t-PAD.b;
  let lo = Math.min(...p.prices, lineVal(p,-2,0), lineVal(p,-2,p.n-1));
  let hi = Math.max(...p.prices, lineVal(p,2,0), lineVal(p,2,p.n-1));
  const q = (hi-lo)*0.06; lo -= q; hi += q;
  const X = i => PAD.l + (p.n>1 ? i/(p.n-1) : .5)*iw, Y = v => PAD.t + (1-(v-lo)/(hi-lo))*ih;
  geom = { X, Y, W, H, iw };

  let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  for (let k=0; k<=6; k++) {
    const v = lo+(hi-lo)*k/6, yy = Y(v);
    s += `<line x1="${PAD.l}" y1="${yy}" x2="${W-PAD.r}" y2="${yy}" stroke="var(--line)"/>`;
    s += `<text x="${PAD.l-9}" y="${yy+4}" text-anchor="end" font-size="11" fill="var(--muted)">${v.toFixed(1)}</text>`;
  }
  const xt = Math.min(7, p.n);
  for (let k=0; k<xt; k++) {
    const i = Math.round(k*(p.n-1)/Math.max(1,xt-1));
    s += `<text x="${X(i)}" y="${H-PAD.b+18}" text-anchor="middle" font-size="11" fill="var(--muted)">${String(p.dates[i]).slice(0,6).replace(/(\d{4})(\d{2})/,'$1/$2')}</text>`;
  }
  BANDS.forEach(b => {
    s += `<line x1="${X(0)}" y1="${Y(lineVal(p,b[1],0))}" x2="${X(p.n-1)}" y2="${Y(lineVal(p,b[1],p.n-1))}" stroke="${b[2]}" stroke-width="1.9"/>`;
    const yv = Y(p.levels[b[0]]);
    const bw = narrow ? 42 : 50;
    s += `<rect x="${W-PAD.r+3}" y="${yv-8}" width="${bw}" height="16" rx="4" fill="${b[2]}"/>`;
    s += `<text x="${W-PAD.r+3+bw/2}" y="${yv+4}" text-anchor="middle" font-size="${narrow?9.5:10.5}" fill="#fff" font-weight="600">${p.levels[b[0]].toFixed(1)}</text>`;
  });
  s += `<polyline fill="none" stroke="var(--fg)" stroke-width="1.25" stroke-linejoin="round" points="${
    p.prices.map((v,i)=>`${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')}"/>`;
  s += `<line id="cross" x1="0" y1="${PAD.t}" x2="0" y2="${H-PAD.b}" stroke="var(--muted)" stroke-dasharray="3 3" opacity="0"/>`;
  s += `<g id="dots"></g><rect x="${PAD.l}" y="${PAD.t}" width="${iw}" height="${ih}" fill="transparent" id="hit"/></svg>`;
  chart.innerHTML = s; chart.appendChild(tip); bind();

  document.getElementById('legend').innerHTML =
    BANDS.map(b => `<span><i style="background:${b[2]}"></i>${b[0]} ${p.levels[b[0]].toFixed(2)}</span>`).join('')
    + `<span><i style="background:var(--fg)"></i>股價 ${p.price.toFixed(2)}</span>`;
}

function bind() {
  const hit = document.getElementById('hit'), cross = document.getElementById('cross');
  const dots = document.getElementById('dots'), svg = chart.querySelector('svg');
  function move(ev) {
    const r = svg.getBoundingClientRect();
    const px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
    let i = Math.round((px-PAD.l)/(geom.iw||1)*(cur.n-1));
    i = Math.max(0, Math.min(cur.n-1, i));
    const x = geom.X(i);
    cross.setAttribute('x1',x); cross.setAttribute('x2',x); cross.setAttribute('opacity','1');
    const items = BANDS.map(b => ({nm:b[0], v:lineVal(cur,b[1],i), c:b[2]}));
    items.push({nm:'價格', v:cur.prices[i], c:'var(--fg)'});
    items.sort((a,b) => b.v-a.v);
    dots.innerHTML = items.map(it =>
      `<circle cx="${x}" cy="${geom.Y(it.v)}" r="3.6" fill="${it.c==='var(--fg)'?'#111':it.c}" stroke="#fff" stroke-width="1.3"/>`).join('');
    tip.innerHTML = `<div class="d">${fmtDate(cur.dates[i])}</div>` + items.map(it =>
      `<div class="r"><span class="dot" style="background:${it.c}"></span><span class="nm">${it.nm}</span><span class="vl">${it.v.toFixed(2)}</span></div>`).join('');
    tip.style.opacity = '1';
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let lx = x+16; if (lx+tw > geom.W) lx = x-tw-16;
    tip.style.left = lx+'px';
    tip.style.top = Math.min(Math.max(geom.Y(cur.prices[i])-th/2, 4), geom.H-th-4)+'px';
  }
  function leave(){ tip.style.opacity='0'; cross.setAttribute('opacity','0'); dots.innerHTML=''; }
  hit.addEventListener('mousemove', move);
  hit.addEventListener('mouseleave', leave);
  hit.addEventListener('touchmove', e => { move(e); e.preventDefault(); }, {passive:false});
  hit.addEventListener('touchend', leave);
}

function pick(i) {
  cur = periods[i];
  [...document.querySelectorAll('#tabs button')].forEach((b,k) => b.classList.toggle('on', k===i));
  document.getElementById('mood').textContent = cur.mood;
  document.getElementById('mood').style.color = MOODC[cur.mood];
  document.getElementById('sig').textContent = cur.sigma.toFixed(2);
  document.getElementById('rng').textContent = cur.range;
  document.getElementById('warnbox').innerHTML = cur.warn ? `<div class="warn">⚠ ${cur.warn}</div>` : '';
  render();
}

// ── 手動查詢台股：FinMind 開放 CORS，可直接由瀏覽器取得 ──
let custom = null;          // 使用者查詢後暫存的標的
const msg = document.getElementById('msg');

function say(text, kind) {
  msg.textContent = text;
  msg.className = 'status on ' + (kind || 'ok');
}
function hide() { msg.className = 'status'; }

function pickPreset() {
  custom = null;
  document.getElementById('code').value = '';
  hide();
  go();
}

async function fetchCode() {
  const raw = document.getElementById('code').value.trim().toUpperCase();
  if (!raw) { say('請先輸入股票代碼。', 'err'); return; }
  if (!/^[0-9]{4,6}[A-Z]?$/.test(raw)) {
    say('請輸入台股代碼（4~6 位數字，如 2412、00878）。此功能僅支援台股。', 'err');
    return;
  }

  say('查詢 ' + raw + ' 中…');
  // 抓 10.5 年，供十年線（2400 個交易日）計算
  const from = new Date(Date.now() - 10.5 * 365.25 * 86400000)
                 .toISOString().slice(0, 10);
  const url = 'https://api.finmindtrade.com/api/v4/data'
            + '?dataset=TaiwanStockPrice&data_id=' + encodeURIComponent(raw)
            + '&start_date=' + from;
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const json = await res.json();
    const rows = (json.data || []).filter(r => r.close > 0);
    if (!rows.length) {
      say('查無 ' + raw + ' 的資料，請確認代碼是否正確。', 'err');
      return;
    }
    rows.sort((a, b) => a.date < b.date ? -1 : 1);
    custom = {
      code: raw,
      label: '自行查詢',
      dates: rows.map(r => +r.date.replace(/-/g, '')),
      closes: rows.map(r => +r.close),
    };
    say('已取得 ' + raw + '　' + rows.length + ' 筆（' + rows[0].date
        + ' ~ ' + rows[rows.length - 1].date + '）', 'ok');
    go();
  } catch (err) {
    say('查詢失敗：' + err.message
        + '。可能是網路問題或 FinMind 服務暫時無法使用，請稍後再試。', 'err');
  }
}

function go() {
  const d = custom || DATA[+document.getElementById('tk').value];
  let ys = [...document.querySelectorAll('#chips input:checked')].map(c => +c.value);
  const raw = document.getElementById('custom').value.trim();
  if (raw) raw.replace(/[,，]/g,' ').split(/\s+/).forEach(t => {
    const v = parseFloat(t);
    if (isFinite(v) && v > 0 && v <= 50) ys.push(v);
  });
  ys = [...new Set(ys)].sort((a,b) => a-b);
  if (!ys.length) ys = [3.5];

  periods = ys.map(y => compute(d, y)).filter(Boolean);
  if (!periods.length) { alert('資料不足，無法分析'); return; }

  document.getElementById('name').textContent =
    custom ? (d.code + '　（即時查詢）') : (d.code + '　' + d.label);
  document.getElementById('px').textContent = '$' + periods[0].price.toLocaleString(
    undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
  document.getElementById('tabs').innerHTML =
    periods.map((p,i) => `<button onclick="pick(${i})">${p.years} 年回歸</button>`).join('');

  document.getElementById('tbl').innerHTML = periods.length < 2 ? '' :
    `<div class="cap">期間比較</div><table><thead><tr><th>線別</th>` +
    periods.map(p => `<th>${p.years} 年</th>`).join('') + `</tr></thead><tbody>` +
    BANDS.map(b => `<tr><td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${b[2]};margin-right:7px"></span>${b[0]}</td>` +
      periods.map(p => `<td>${p.levels[b[0]].toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}</td>`).join('') + `</tr>`).join('') +
    `<tr><td>市場情緒</td>` + periods.map(p => `<td style="color:${MOODC[p.mood]};font-weight:600">${p.mood}</td>`).join('') + `</tr>` +
    `<tr><td>通道內位置</td>` + periods.map(p => `<td>${p.pos.toFixed(1)}%</td>`).join('') + `</tr>` +
    `</tbody></table>`;

  // 價位總覽：五線譜各期間 + 各條均線 + 現價，合併後由高到低排序
  const price = periods[0].price;
  const mas = movingAverages(d.closes);
  let items = [];
  periods.forEach(p => BANDS.forEach(b =>
    items.push({ v:p.levels[b[0]], c:b[2], cat:`五線譜 ${p.years} 年`, nm:b[0] })));
  mas.filter(m => m.ok).forEach(m =>
    items.push({ v:m.v, c:MACOLOR, cat:"移動平均", nm:`${m.nm}（${m.n}MA）` }));
  items.push({ v:price, c:"#111", cat:"現價", nm:"最新收盤", now:true });
  items.sort((a,b) => b.v - a.v);

  const fmt = x => x.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
  const miss = mas.filter(m => !m.ok).map(m => `${m.nm}（${m.n}MA）`);
  document.getElementById('ovw').innerHTML =
    `<div class="cap">價位總覽（由高到低）</div><table><thead><tr><th>價位</th><th>類別</th>` +
    `<th style="text-align:left">說明</th><th>現價乖離</th></tr></thead><tbody>` +
    items.map(it => `<tr${it.now?' style="background:var(--hl);font-weight:700"':''}>` +
      `<td>${fmt(it.v)}</td><td><span style="display:inline-block;width:10px;height:10px;` +
      `border-radius:50%;background:${it.c};margin-right:7px"></span>${it.cat}</td>` +
      `<td style="text-align:left">${it.nm}${it.now?'　◀ 現在位置':''}</td>` +
      `<td>${it.now?'':((price-it.v)/it.v*100).toFixed(2).replace(/^(?!-)/,'+')+'%'}</td></tr>`).join('') +
    `</tbody></table>` +
    (miss.length ? `<div style="font-size:12.5px;color:var(--muted);margin-top:8px">` +
      `※ 資料不足未列出：${miss.join('、')}</div>` : '');

  pick(0);
}

go();
addEventListener('resize', () => { if (cur) render(); });
</script>
</body>
</html>
"""


def load_tickers(path):
    """從文字檔讀取股票清單；每行格式為「代碼,名稱」，# 開頭為註解。"""
    if not path or not os.path.exists(path):
        return TICKERS
    items = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.replace("\t", ",").split(",")]
            if parts[0]:
                items.append((parts[0], parts[1] if len(parts) > 1 else parts[0]))
    return items or TICKERS


def main():
    parser = argparse.ArgumentParser(description="產生免安裝的樂活五線譜 HTML")
    parser.add_argument("-o", "--output", default="樂活五線譜.html", help="輸出檔名")
    parser.add_argument("-t", "--tickers", default="tickers.txt",
                        help="股票清單檔（每行「代碼,名稱」），不存在時用內建清單")
    parser.add_argument("-y", "--years", type=float, default=10.5,
                        help="嵌入幾年的歷史資料，預設 10.5（供十年線計算）")
    args = parser.parse_args()

    tickers = load_tickers(args.tickers)
    end = dt.date.today()
    start = end - dt.timedelta(days=round(365.25 * args.years))

    payload, failed = [], []
    for code, label in tickers:
        try:
            _sym, _name, rows, intraday = core.resolve(code, start, end)
            if intraday:                       # 排除未收盤的盤中價
                rows = [r for r in rows if r[0] != intraday["date"]]
            if not rows:
                raise ValueError("無可用資料")
            payload.append({
                "code": code, "label": label,
                "dates": [int(r[0].strftime("%Y%m%d")) for r in rows],
                "closes": [round(r[1], 2) for r in rows],
            })
            print(f"  {code:8} {label:12} {len(rows):5} 筆　最新 {rows[-1][1]:,.2f}")
        except Exception as exc:               # noqa: BLE001
            failed.append(code)
            print(f"  {code:8} 略過（{exc}）")

    if not payload:
        raise SystemExit("所有標的都抓取失敗，未產生檔案。")
    if failed:
        print(f"\n  ⚠ 下列標的抓取失敗，未納入：{'、'.join(failed)}")

    latest = max(max(p["dates"]) for p in payload)
    as_of = f"{str(latest)[:4]}/{str(latest)[4:6]}/{str(latest)[6:]}"

    html = (TEMPLATE
            .replace("__ASOF__", as_of)
            .replace("__DATA__", json.dumps(payload, ensure_ascii=False,
                                            separators=(",", ":"))))

    outdir = os.path.dirname(args.output)
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"\n  已產生 {args.output}（{os.path.getsize(args.output)/1024:.0f} KB）"
          f"　資料日期 {as_of}")


if __name__ == "__main__":
    main()
