#!/usr/bin/env python3
"""
樂活五線譜 (Lohas Five-Line Chart) CLI  v2
------------------------------------------------
以線性迴歸 + 標準差計算股價位階，支援多期間同時比較。

演算法（已對照 sentimentinsideout.com 實測驗證，誤差 < 0.15）：
  1. 取近 N 年日收盤價（未還原權息）
  2. x = 交易日序號, y = 收盤價，跑最小平方線性迴歸 → 趨勢線
  3. σ = 殘差標準差
  4. 五條線 = 趨勢線, ±1σ, ±2σ

相依套件：numpy（必要）、matplotlib（僅 PNG 輸出時需要）
資料來源：Yahoo Finance chart API（以標準函式庫 urllib 存取，不需 yfinance）
"""

import argparse
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request

MIN_PYTHON = (3, 8)
if sys.version_info < MIN_PYTHON:
    raise SystemExit(
        f"需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} 以上，"
        f"目前為 {sys.version_info[0]}.{sys.version_info[1]}。\n"
        f"請至 https://www.python.org/downloads/ 安裝新版。")

import numpy as np

# ── 五線設定：(名稱, 標準差倍數, 顏色) ────────────────────────────
BANDS = [
    ("極度貪婪", 2.0, "#d81b60"),
    ("貪婪", 1.0, "#f48fb1"),
    ("趨勢線", 0.0, "#546e7a"),
    ("恐懼", -1.0, "#4fc3f7"),
    ("極度恐懼", -2.0, "#1565c0"),
]

MOOD_COLORS = {"極度貪婪": "#d81b60", "貪婪": "#ec7fa4", "中性": "#546e7a",
               "恐懼": "#4fc3f7", "極度恐懼": "#1565c0"}

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


# ── 資料抓取 ──────────────────────────────────────────────────
def normalize_ticker(code: str) -> list:
    """純數字代碼自動補台股後綴：先試上市 .TW，再試上櫃 .TWO。"""
    code = code.strip().upper()
    if code.isdigit() or (len(code) > 1 and code[:-1].isdigit() and code[-1].isalpha()):
        return [f"{code}.TW", f"{code}.TWO"]
    return [code]


def fetch_prices(ticker: str, start: dt.date, end: dt.date):
    """回傳 ([(date, close), ...], 名稱)，已濾掉無成交資料的日子。"""
    params = urllib.parse.urlencode({
        "period1": int(dt.datetime.combine(start, dt.time()).timestamp()),
        "period2": int(dt.datetime.combine(end + dt.timedelta(days=1), dt.time()).timestamp()),
        "interval": "1d",
    })
    req = urllib.request.Request(
        f"{YAHOO_URL.format(urllib.parse.quote(ticker))}?{params}",
        headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.load(resp)

    result = payload.get("chart", {}).get("result")
    if not result:
        raise LookupError(f"查無 {ticker} 的資料")

    node = result[0]
    meta = node.get("meta", {})
    stamps = node.get("timestamp") or []
    closes = node["indicators"]["quote"][0].get("close") or []
    tz = meta.get("gmtoffset", 0)

    rows = []
    for stamp, close in zip(stamps, closes):
        if close is None:
            continue
        day = dt.datetime.fromtimestamp(stamp + tz, dt.timezone.utc).date()
        if day <= end:
            rows.append((day, float(close)))
    if not rows:
        raise LookupError(f"{ticker} 在指定區間內沒有價格資料")

    # 判斷最後一筆是否為「尚未收盤的盤中價」
    intraday = None
    period = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    quote_time = meta.get("regularMarketTime")
    if period.get("end") and quote_time and quote_time < period["end"]:
        last_day = dt.datetime.fromtimestamp(quote_time + tz, dt.timezone.utc)
        if rows and rows[-1][0] == last_day.date():
            intraday = {
                "date": last_day.date(),
                "price": rows[-1][1],
                "quote_time": last_day.strftime("%H:%M"),
                "close_time": dt.datetime.fromtimestamp(period["end"] + tz,
                                                        dt.timezone.utc).strftime("%H:%M"),
            }

    name = meta.get("longName") or meta.get("shortName") or ticker
    return rows, name, intraday


def resolve(code: str, start: dt.date, end: dt.date):
    """依序嘗試候選代碼，回傳 (代碼, 名稱, 資料, 盤中資訊)。"""
    errors = []
    for candidate in normalize_ticker(code):
        try:
            rows, name, intraday = fetch_prices(candidate, start, end)
            return candidate, name, rows, intraday
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{candidate}: {exc}")
    raise SystemExit("抓取失敗 →\n  " + "\n  ".join(errors))


# ── 核心運算 ──────────────────────────────────────────────────
def five_lines(rows):
    """回傳 (五條線今日價位 dict, sigma, 趨勢線陣列, 日期, 價格)。"""
    days = [r[0] for r in rows]
    prices = np.array([r[1] for r in rows], dtype=float)
    x = np.arange(len(prices), dtype=float)

    slope, intercept = np.polyfit(x, prices, 1)
    trend = intercept + slope * x
    sigma = float(np.std(prices - trend, ddof=0))

    today = float(trend[-1])
    levels = {name: today + mult * sigma for name, mult, _ in BANDS}
    return levels, sigma, trend, days, prices


def classify(price: float, levels: dict) -> str:
    """依價格落點判斷市場情緒。"""
    if price > levels["極度貪婪"]:
        return "極度貪婪"
    if price > levels["貪婪"]:
        return "貪婪"
    if price >= levels["恐懼"]:
        return "中性"
    if price >= levels["極度恐懼"]:
        return "恐懼"
    return "極度恐懼"


def channel_position(price: float, levels: dict) -> float:
    """把價格換算成通道內相對位置（0% = -2σ, 100% = +2σ）。"""
    low, high = levels["極度恐懼"], levels["極度貪婪"]
    return (price - low) / (high - low) * 100 if high > low else 50.0


MA_DEFS = [("月線", 20), ("季線", 60), ("半年線", 120), ("年線", 240),
           ("兩年線", 480), ("五年線", 1200), ("十年線", 2400)]

MA_COLOR = "#8b7355"


def moving_averages(rows):
    """計算各期間簡單移動平均；資料不足者標記 ok=False。"""
    closes = [r[1] for r in rows]
    result = []
    for name, days in MA_DEFS:
        if len(closes) >= days:
            result.append({"name": name, "days": days,
                           "value": sum(closes[-days:]) / days, "ok": True})
        else:
            result.append({"name": name, "days": days, "value": None,
                           "ok": False, "have": len(closes)})
    return result


def price_overview(periods, mas, price):
    """把五線譜各期間的線價、各條均線與現價合併後由高到低排序。"""
    items = []
    for period in periods:
        for band, _, color in BANDS:
            items.append({"value": period["levels"][band], "color": color,
                          "cat": f"五線譜 {period['years']:g} 年", "name": band})
    for ma in mas:
        if ma["ok"]:
            items.append({"value": ma["value"], "color": MA_COLOR,
                          "cat": "移動平均", "name": f"{ma['name']}（{ma['days']}MA）"})
    items.append({"value": price, "color": "#111111", "cat": "現價", "name": "最新收盤"})
    items.sort(key=lambda x: -x["value"])
    return items


def analyze(all_rows, years: float, end: dt.date) -> dict:
    """從完整資料切出指定年限的區間並計算，回傳一個期間的完整結果。"""
    start = end - dt.timedelta(days=round(365.25 * years))
    rows = [r for r in all_rows if r[0] >= start]
    if len(rows) < 3:
        raise SystemExit(f"{years} 年區間內資料不足（僅 {len(rows)} 筆）")

    levels, sigma, trend, days, prices = five_lines(rows)
    price = float(prices[-1])
    actual = (days[-1] - days[0]).days / 365.25

    warn = ""
    if actual < years * 0.9:
        warn = (f"要求 {years} 年，實際僅取得 {actual:.2f} 年（{len(days)} 個交易日）。"
                f"多為新上市標的所致，五條線僅供參考，統計意義有限。")
    elif len(days) < 60:
        warn = f"樣本僅 {len(days)} 個交易日，迴歸結果不穩定。"

    return {"years": years, "levels": levels, "sigma": sigma, "trend": trend,
            "days": days, "prices": prices, "price": price,
            "actual_years": actual, "mood": classify(price, levels),
            "position": channel_position(price, levels), "warning": warn}


# ── 文字輸出 ──────────────────────────────────────────────────
def pad(text: str, width: int) -> str:
    """以顯示寬度對齊（中文字算 2 格）。"""
    w = sum(2 if ord(c) > 0x2E80 else 1 for c in text)
    return text + " " * max(0, width - w)


def print_period(period: dict):
    price = period["price"]
    print(f"  ── {period['years']} 年回歸 "
          f"（{period['days'][0]} ~ {period['days'][-1]}，"
          f"{len(period['days'])} 個交易日，σ={period['sigma']:.2f}）")
    if period["warning"]:
        print(f"     ⚠ {period['warning']}")
    for band, _, _ in BANDS:
        value = period["levels"][band]
        gap = (price - value) / value * 100
        mark = " ←" if band == period["mood"] else ""
        print(f"     {pad(band, 10)}{value:>10,.2f}{gap:>+11.2f}%{mark}")
    print(f"     {pad('市場情緒', 10)}{pad(period['mood'], 10)}"
          f"通道內位置 {period['position']:.1f}%")
    print()


def print_overview(items, mas):
    """列印合併排序後的價位總覽。"""
    print("  ══ 價位總覽（由高到低）══")
    print("  " + pad("價位", 12) + pad("類別", 16) + "說明")
    print("  " + "─" * 48)
    for it in items:
        mark = "  ◀ 現價" if it["cat"] == "現價" else ""
        print("  " + pad(f"{it['value']:,.2f}", 12) + pad(it["cat"], 16)
              + it["name"] + mark)
    missing = [f"{m['name']}({m['days']}MA)" for m in mas if not m["ok"]]
    if missing:
        print(f"  ※ 資料不足未列出：{'、'.join(missing)}")
    print()


def print_report(code, name, periods, intraday=None, skipped=None, mas=None):
    price = periods[0]["price"]
    print()
    print(f"  {name}  ({code})")
    if intraday:
        print(f"  盤中即時　${price:,.2f}　"
              f"（{intraday['date']} {intraday['quote_time']} 報價，"
              f"{intraday['close_time']} 才收盤，數值仍會變動）")
    else:
        print(f"  最新收盤　${price:,.2f}　（{periods[0]['days'][-1]}）")
    if skipped:
        print(f"  ※ 已排除 {skipped['date']} 盤中未收盤資料"
              f"（現價 {skipped['price']:,.2f}，{skipped['close_time']} 收盤）；"
              f"加 --live 可納入")
    print()
    for period in periods:
        print_period(period)

    if len(periods) > 1:
        print("  ══ 期間比較 ══")
        head = "  " + pad("年限", 8) + "".join(pad(b, 11) for b, _, _ in BANDS) + "情緒"
        print(head)
        print("  " + "─" * (len(head) - 2))
        for period in periods:
            row = "  " + pad(f"{period['years']}年", 8)
            row += "".join(f"{period['levels'][b]:>9,.2f}  " for b, _, _ in BANDS)
            row += period["mood"]
            print(row)
        print()
        moods = {p["mood"] for p in periods}
        if len(moods) > 1:
            print("  ※ 不同回歸期間結論不一致，代表短線與長線位階背離，")
            print("    判讀時請留意你關心的是哪一個時間尺度。")
            print()

    if mas:
        print_overview(price_overview(periods, mas, price), mas)


# ── HTML 輸出 ─────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { --bg:#fff; --fg:#1a1a1a; --muted:#6b7280; --grid:#e5e7eb; --card:#fff;
          --tab:#f3f4f6; --hl:#fff3c4; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#15161a; --fg:#e9e9ee; --muted:#9aa0ac; --grid:#2c2f37; --card:#1f2128;
            --tab:#242730; --hl:#3d3a1f; }
  }
  * { box-sizing:border-box; }
  body { margin:0; padding:24px; background:var(--bg); color:var(--fg);
         font-family:-apple-system,"PingFang TC","Noto Sans TC","Microsoft JhengHei",sans-serif; }
  .wrap { max-width:1180px; margin:0 auto; }
  h1 { font-size:19px; margin:0 0 3px; font-weight:600; }
  .sub { color:var(--muted); font-size:13px; margin-bottom:16px; }
  .stats { display:flex; gap:34px; flex-wrap:wrap; margin-bottom:16px; }
  .stat .k { font-size:12px; color:var(--muted); margin-bottom:3px; }
  .stat .v { font-size:22px; font-weight:600; }
  .tabs { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px; }
  .tabs button { border:1px solid var(--grid); background:var(--tab); color:var(--muted);
     padding:7px 16px; border-radius:8px; font-size:13.5px; cursor:pointer; font-weight:500;
     font-family:inherit; }
  .tabs button.on { background:var(--fg); color:var(--bg); border-color:var(--fg); }
  .warn { background:#fef3c7; color:#92400e; border-radius:8px; padding:10px 14px;
          font-size:13px; margin-bottom:14px; }
  .live { background:#e0f2fe; color:#075985; border-radius:8px; padding:9px 13px;
          font-size:12.5px; margin-bottom:14px; display:inline-block; }
  @media (prefers-color-scheme: dark) { .live { background:#0c2b3d; color:#7dd3fc; } }
  @media (prefers-color-scheme: dark) { .warn { background:#3a2f12; color:#fcd34d; } }
  #chart { position:relative; width:100%; }
  svg { display:block; width:100%; overflow:visible; }
  #tip { position:absolute; pointer-events:none; opacity:0; transition:opacity .1s;
         background:var(--card); border:1px solid var(--grid); border-radius:8px;
         padding:9px 11px; font-size:12.5px; line-height:1.65;
         box-shadow:0 6px 20px rgba(0,0,0,.13); white-space:nowrap; z-index:5; }
  #tip .d { font-weight:600; margin-bottom:4px; }
  #tip .row { display:flex; align-items:center; gap:7px; }
  #tip .dot { width:9px; height:9px; border-radius:50%; flex:none; }
  #tip .nm { flex:1; } #tip .vl { font-variant-numeric:tabular-nums; font-weight:600; }
  .legend { display:flex; gap:16px; flex-wrap:wrap; margin-top:12px; font-size:12.5px;
            color:var(--muted); }
  .legend span { display:flex; align-items:center; gap:6px; }
  .legend i { width:14px; height:3px; border-radius:2px; display:block; }
  table { border-collapse:collapse; width:100%; margin-top:26px; font-size:13px; }
  th,td { padding:8px 10px; text-align:right; border-bottom:1px solid var(--grid); }
  th:first-child, td:first-child { text-align:left; }
  th { color:var(--muted); font-weight:500; }
  td { font-variant-numeric:tabular-nums; }
  .cap { font-size:13px; color:var(--muted); margin:26px 0 -18px; font-weight:600; }
  .note { font-size:12.5px; color:var(--muted); margin-top:14px; line-height:1.7; }
</style>
</head>
<body>
<div class="wrap">
  <h1>__NAME__</h1>
  <div class="sub">樂活五線譜　|　基準日 __ASOF__</div>
  __INTRADAY__
  <div class="stats">
    <div class="stat"><div class="k">__PRICELABEL__</div><div class="v">$__PRICE__</div></div>
    <div class="stat"><div class="k">市場情緒</div><div class="v" id="mood"></div></div>
    <div class="stat"><div class="k">標準差 σ</div><div class="v" id="sig"></div></div>
    <div class="stat"><div class="k">回歸區間</div><div class="v" id="rng" style="font-size:15px;padding-top:5px"></div></div>
  </div>
  <div class="tabs" id="tabs"></div>
  <div id="warnbox"></div>
  <div id="chart"><div id="tip"></div></div>
  <div class="legend" id="legend"></div>
  __TABLE__
  __OVERVIEW__
  <div class="note">演算法：取區間內日收盤價（未還原權息），以交易日序號為 x 跑最小平方線性迴歸得趨勢線，
  再以殘差標準差 σ 畫出 ±1σ、±2σ 共五條線。<br>本工具僅為技術面數值計算，不構成投資建議。</div>
</div>
<script>
const ALL = __DATA__;
const PAD = { t:14, r:62, b:30, l:52 };
const chart = document.getElementById('chart');
const tip = document.getElementById('tip');
let geom = null, D = ALL.periods[0];

function lineVal(band, i) {
  const t = D.n > 1 ? i / (D.n - 1) : 0;
  return (D.trend0 + (D.trendN - D.trend0) * t) + band.mult * D.sigma;
}

function render() {
  const W = chart.clientWidth, H = Math.max(380, Math.min(560, W * 0.5));
  const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b;
  const last = D.bands[D.bands.length - 1], first = D.bands[0];

  let lo = Math.min(...D.prices, lineVal(last, 0), lineVal(last, D.n - 1));
  let hi = Math.max(...D.prices, lineVal(first, 0), lineVal(first, D.n - 1));
  const p = (hi - lo) * 0.06; lo -= p; hi += p;

  const X = i => PAD.l + (D.n > 1 ? i / (D.n - 1) : 0.5) * iw;
  const Y = v => PAD.t + (1 - (v - lo) / (hi - lo)) * ih;
  geom = { X, Y, W, H, iw, ih };

  let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  for (let k = 0; k <= 6; k++) {
    const v = lo + (hi - lo) * k / 6, y = Y(v);
    s += `<line x1="${PAD.l}" y1="${y}" x2="${W-PAD.r}" y2="${y}" stroke="var(--grid)"/>`;
    s += `<text x="${PAD.l-9}" y="${y+4}" text-anchor="end" font-size="11" fill="var(--muted)">${v.toFixed(1)}</text>`;
  }
  const xt = Math.min(7, D.n);
  for (let k = 0; k < xt; k++) {
    const i = Math.round(k * (D.n - 1) / Math.max(1, xt - 1));
    s += `<text x="${X(i)}" y="${H-PAD.b+18}" text-anchor="middle" font-size="11" fill="var(--muted)">${D.dates[i].slice(0,7)}</text>`;
  }
  D.bands.forEach(b => {
    s += `<line x1="${X(0)}" y1="${Y(lineVal(b,0))}" x2="${X(D.n-1)}" y2="${Y(lineVal(b,D.n-1))}" stroke="${b.color}" stroke-width="1.9"/>`;
    const yv = Y(lineVal(b, D.n-1));
    s += `<rect x="${W-PAD.r+5}" y="${yv-9}" width="46" height="18" rx="4" fill="${b.color}"/>`;
    s += `<text x="${W-PAD.r+28}" y="${yv+4}" text-anchor="middle" font-size="11" fill="#fff" font-weight="600">${b.today.toFixed(1)}</text>`;
  });
  s += `<polyline fill="none" stroke="var(--fg)" stroke-width="1.25" stroke-linejoin="round" points="${
    D.prices.map((v,i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')}"/>`;
  s += `<line id="cross" x1="0" y1="${PAD.t}" x2="0" y2="${H-PAD.b}" stroke="var(--muted)" stroke-dasharray="3 3" opacity="0"/>`;
  s += `<g id="dots"></g>`;
  s += `<rect x="${PAD.l}" y="${PAD.t}" width="${iw}" height="${ih}" fill="transparent" id="hit"/></svg>`;

  chart.innerHTML = s;
  chart.appendChild(tip);
  bind();

  document.getElementById('legend').innerHTML =
    D.bands.map(b => `<span><i style="background:${b.color}"></i>${b.name} ${b.today.toFixed(2)}</span>`).join('') +
    `<span><i style="background:var(--fg)"></i>股價 ${D.prices[D.n-1].toFixed(2)}</span>`;
}

function bind() {
  const hit = document.getElementById('hit');
  const cross = document.getElementById('cross');
  const dots = document.getElementById('dots');
  const svg = chart.querySelector('svg');

  function move(ev) {
    const r = svg.getBoundingClientRect();
    const px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
    let i = Math.round((px - PAD.l) / (geom.iw || 1) * (D.n - 1));
    i = Math.max(0, Math.min(D.n - 1, i));
    const x = geom.X(i);
    cross.setAttribute('x1', x); cross.setAttribute('x2', x); cross.setAttribute('opacity', '1');

    const items = D.bands.map(b => ({ nm:b.name, v:lineVal(b,i), c:b.color }));
    items.push({ nm:'價格', v:D.prices[i], c:'var(--fg)' });
    items.sort((a,b) => b.v - a.v);

    dots.innerHTML = items.map(it =>
      `<circle cx="${x}" cy="${geom.Y(it.v)}" r="3.6" fill="${it.c==='var(--fg)'?'#111':it.c}" stroke="#fff" stroke-width="1.3"/>`).join('');
    tip.innerHTML = `<div class="d">${D.dates[i].replace(/-/g,'/')}</div>` + items.map(it =>
      `<div class="row"><span class="dot" style="background:${it.c}"></span><span class="nm">${it.nm}</span><span class="vl">${it.v.toFixed(2)}</span></div>`).join('');
    tip.style.opacity = '1';
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let lx = x + 16; if (lx + tw > geom.W) lx = x - tw - 16;
    tip.style.left = lx + 'px';
    tip.style.top = Math.min(Math.max(geom.Y(D.prices[i]) - th/2, 4), geom.H - th - 4) + 'px';
  }
  function leave() { tip.style.opacity='0'; cross.setAttribute('opacity','0'); dots.innerHTML=''; }

  hit.addEventListener('mousemove', move);
  hit.addEventListener('mouseleave', leave);
  hit.addEventListener('touchmove', e => { move(e); e.preventDefault(); }, { passive:false });
  hit.addEventListener('touchend', leave);
}

function select(idx) {
  D = ALL.periods[idx];
  [...document.querySelectorAll('#tabs button')].forEach((b,i) => b.classList.toggle('on', i===idx));
  const mood = document.getElementById('mood');
  mood.textContent = D.mood; mood.style.color = D.moodColor;
  document.getElementById('sig').textContent = D.sigma.toFixed(2);
  document.getElementById('rng').textContent = D.range;
  document.getElementById('warnbox').innerHTML = D.warning ? `<div class="warn">⚠ ${D.warning}</div>` : '';
  render();
}

document.getElementById('tabs').innerHTML =
  ALL.periods.map((p,i) => `<button onclick="select(${i})">${p.years} 年回歸</button>`).join('');
select(0);
addEventListener('resize', render);
</script>
</body>
</html>
"""


def build_overview_table(periods, mas, price) -> str:
    """產生「價位總覽」表格：五線譜各期間線價 + 各條均線 + 現價，由高到低排序。"""
    if not mas:
        return ""
    rows = ""
    for it in price_overview(periods, mas, price):
        is_now = it["cat"] == "現價"
        style = ' style="background:var(--hl);font-weight:700"' if is_now else ""
        gap = "" if is_now else f'{(price - it["value"]) / it["value"] * 100:+.2f}%'
        rows += (f'<tr{style}><td>{it["value"]:,.2f}</td>'
                 f'<td><span style="display:inline-block;width:10px;height:10px;'
                 f'border-radius:50%;background:{it["color"]};margin-right:7px"></span>'
                 f'{it["cat"]}</td><td style="text-align:left">{it["name"]}'
                 f'{"　◀ 現在位置" if is_now else ""}</td><td>{gap}</td></tr>')

    missing = [f'{m["name"]}（{m["days"]}MA）' for m in mas if not m["ok"]]
    note = (f'<div style="font-size:12.5px;color:var(--muted);margin-top:8px">'
            f'※ 資料不足未列出：{"、".join(missing)}</div>') if missing else ""

    return ('<div class="cap">價位總覽（由高到低）</div>'
            '<table><thead><tr><th>價位</th><th>類別</th>'
            '<th style="text-align:left">說明</th><th>現價乖離</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>{note}')


def build_table(periods) -> str:
    """多期間時產生比較表格 HTML。"""
    if len(periods) < 2:
        return ""
    head = "".join(f"<th>{p['years']} 年</th>" for p in periods)
    rows = ""
    for band, _, color in BANDS:
        cells = "".join(f"<td>{p['levels'][band]:,.2f}</td>" for p in periods)
        rows += (f'<tr><td><span style="display:inline-block;width:10px;height:10px;'
                 f'border-radius:50%;background:{color};margin-right:7px"></span>{band}</td>{cells}</tr>')
    moods = "".join(
        f'<td style="color:{MOOD_COLORS.get(p["mood"], "#546e7a")};font-weight:600">{p["mood"]}</td>'
        for p in periods)
    pos = "".join(f"<td>{p['position']:.1f}%</td>" for p in periods)
    return (f'<div class="cap">期間比較</div><table><thead><tr><th>線別</th>{head}</tr></thead>'
            f'<tbody>{rows}<tr><td>市場情緒</td>{moods}</tr>'
            f'<tr><td>通道內位置</td>{pos}</tr></tbody></table>')


def build_html(code, name, periods, as_of, intraday=None, mas=None) -> str:
    """組出完整的互動式 HTML 字串（供檔案輸出或 GUI 內嵌重用）。"""
    data = {"periods": []}
    for period in periods:
        data["periods"].append({
            "years": period["years"],
            "dates": [d.isoformat() for d in period["days"]],
            "prices": [round(float(v), 4) for v in period["prices"]],
            "n": len(period["days"]),
            "trend0": round(float(period["trend"][0]), 6),
            "trendN": round(float(period["trend"][-1]), 6),
            "sigma": round(period["sigma"], 6),
            "mood": period["mood"],
            "moodColor": MOOD_COLORS.get(period["mood"], "#546e7a"),
            "range": f"{period['days'][0]} ~ {period['days'][-1]}",
            "warning": period["warning"],
            "bands": [{"name": n, "mult": m, "color": c, "today": round(period["levels"][n], 4)}
                      for n, m, c in BANDS],
        })

    if intraday:
        live = (f'<div class="live">● 盤中即時價　{intraday["date"]} '
                f'{intraday["quote_time"]} 報價，{intraday["close_time"]} 才收盤，'
                f'數值與五線譜位階仍會變動</div>')
    else:
        live = ""

    html = (HTML_TEMPLATE
            .replace("__TITLE__", f"{name} 樂活五線譜")
            .replace("__NAME__", f"{name}（{code}）")
            .replace("__ASOF__", str(as_of))
            .replace("__INTRADAY__", live)
            .replace("__PRICELABEL__", "盤中即時" if intraday else "最新收盤")
            .replace("__PRICE__", f"{periods[0]['price']:,.2f}")
            .replace("__TABLE__", build_table(periods))
            .replace("__OVERVIEW__", build_overview_table(periods, mas,
                                                          periods[0]["price"]))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))

    return html


def draw_html(path, code, name, periods, as_of, intraday=None, mas=None):
    """輸出零依賴、可離線開啟的多期間互動式 HTML 檔。"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_html(code, name, periods, as_of, intraday, mas))
    return path


def draw_chart(path, code, name, period):
    """輸出靜態 PNG（需 matplotlib）。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    for cand in ["PingFang TC", "Heiti TC", "Microsoft JhengHei",
                 "Noto Sans CJK TC", "Noto Sans CJK JP", "WenQuanYi Zen Hei"]:
        if any(f.name == cand for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.sans-serif"] = [cand]
            break
    plt.rcParams["axes.unicode_minus"] = False

    days, prices, trend = period["days"], period["prices"], period["trend"]
    sigma, levels = period["sigma"], period["levels"]

    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=130)
    for band, mult, color in BANDS:
        ax.plot(days, trend + mult * sigma, color=color, lw=1.6,
                label=f"{band}  {levels[band]:.2f}")
        ax.annotate(f"{levels[band]:.1f}", (days[-1], trend[-1] + mult * sigma),
                    xytext=(6, 0), textcoords="offset points", color="white",
                    fontsize=8, va="center",
                    bbox=dict(boxstyle="round,pad=0.25", fc=color, ec="none"))
    ax.plot(days, prices, color="#111", lw=1.1, label=f"股價  {period['price']:.2f}")
    ax.scatter([days[-1]], [period["price"]], color="#111", s=28, zorder=5)
    ax.set_title(f"{name}（{code}）　樂活五線譜　{period['years']} 年回歸　—　"
                 f"市場情緒：{period['mood']}", fontsize=13, pad=14)
    ax.set_ylabel("價格")
    ax.grid(alpha=0.25, lw=0.6)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    ax.margins(x=0.02)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ── 互動輸入 ──────────────────────────────────────────────────
PRESET_TICKERS = [
    ("0050", "元大台灣50"),
    ("0056", "元大高股息"),
    ("006208", "富邦台50"),
    ("2330", "台積電"),
    ("009816", "凱基台灣50"),
    ("^TWII", "台股加權指數"),
]

PRESET_YEARS = [
    ([1.0], "1 年（短期）"),
    ([3.5], "3.5 年（樂活五線譜標準）"),
    ([5.0], "5 年（中長期）"),
    ([10.0], "10 年（長期）"),
    ([1.0, 3.5, 5.0, 10.0], "1 / 3.5 / 5 / 10 全部比較"),
]


def ask(prompt: str, default: str = "") -> str:
    """讀取一行輸入；EOF 或空白時回傳預設值。"""
    try:
        value = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit("已取消。")
    return value or default


def choose_ticker() -> str:
    """股票代碼：預設清單 + 自行輸入欄位。"""
    print("\n  ── 選擇股票 ──")
    for i, (code, label) in enumerate(PRESET_TICKERS, 1):
        print(f"    {i}) {code:<8}{label}")
    print(f"    {len(PRESET_TICKERS) + 1}) 自行輸入代碼")

    while True:
        raw = ask(f"\n  請選擇 1-{len(PRESET_TICKERS) + 1}（預設 1）：", "1")
        if raw.isdigit() and 1 <= int(raw) <= len(PRESET_TICKERS):
            code = PRESET_TICKERS[int(raw) - 1][0]
            print(f"  → {code}")
            return code
        if raw.isdigit() and int(raw) == len(PRESET_TICKERS) + 1:
            code = ask("  請輸入股票代碼（台股數字如 2454，美股如 NVDA；"
                       "Enter 返回選單）：")
            if code:
                return code
            continue
        print("  ✗ 請輸入清單中的編號。")


def parse_years(raw: str):
    """解析年限字串，支援空白或逗號分隔的多個數值。"""
    values = []
    for token in raw.replace(",", " ").replace("，", " ").split():
        token = token.rstrip("年y Y")
        try:
            value = float(token)
        except ValueError:
            raise ValueError(f"無法辨識的年限：{token}")
        if not 0 < value <= 50:
            raise ValueError(f"年限需介於 0 與 50 之間：{value}")
        values.append(value)
    return values


def choose_years():
    """回歸年限：預設選項 + 自行輸入欄位。"""
    print("\n  ── 選擇回歸年限 ──")
    for i, (_, label) in enumerate(PRESET_YEARS, 1):
        print(f"    {i}) {label}")
    print(f"    {len(PRESET_YEARS) + 1}) 自行輸入年限")

    while True:
        raw = ask(f"\n  請選擇 1-{len(PRESET_YEARS) + 1}（預設 5）：",
                  str(len(PRESET_YEARS)))
        if raw.isdigit() and 1 <= int(raw) <= len(PRESET_YEARS):
            years = PRESET_YEARS[int(raw) - 1][0]
            print(f"  → {' / '.join(f'{y:g}' for y in years)} 年")
            return list(years)
        if raw.isdigit() and int(raw) == len(PRESET_YEARS) + 1:
            while True:
                custom = ask("  請輸入年限，可空白分隔多個（例：0.5 2 7.5；"
                             "Enter 返回選單）：")
                if not custom:
                    break
                try:
                    years = parse_years(custom)
                except ValueError as exc:
                    print(f"  ✗ {exc}　請重新輸入。")
                    continue
                if years:
                    print(f"  → {' / '.join(f'{y:g}' for y in years)} 年")
                    return years
            continue
        print("  ✗ 請輸入清單中的編號。")


# ── 主程式 ────────────────────────────────────────────────────
def run(ticker, years_list, args, end):
    """執行一次完整分析並輸出。"""
    # 需涵蓋最長的迴歸年限與最長均線（十年線 2400 個交易日 ≈ 10 年）
    span = max(max(years_list), 10.5)
    start = end - dt.timedelta(days=round(365.25 * span) + 10)
    code, name, all_rows, intraday = resolve(ticker, start, end)

    # 預設排除未收盤的盤中價：五線譜以收盤價定義
    skipped = None
    if intraday and not args.live:
        all_rows = [r for r in all_rows if r[0] != intraday["date"]]
        if not all_rows:
            raise SystemExit("排除盤中資料後已無可用資料，請加 --live 納入盤中價。")
        skipped, intraday = intraday, None
        end = all_rows[-1][0]

    periods = [analyze(all_rows, y, end) for y in years_list]
    mas = moving_averages(all_rows)
    print_report(code, name, periods, intraday, skipped, mas)

    if args.no_chart:
        return

    stem = args.output or f"{code.replace('.', '_')}_" + "_".join(
        f"{y:g}y" for y in years_list)
    made = []
    if args.format in ("html", "both"):
        made.append(draw_html(f"{stem}.html", code, name, periods, end, intraday, mas))
    if args.format in ("png", "both"):
        for period in periods:
            made.append(draw_chart(f"{stem}_{period['years']:g}y.png", code, name, period))

    for path in made:
        print(f"  圖表已輸出 → {path}")
    print()

    if args.open and made:
        import subprocess
        subprocess.run(["open", made[0]], check=False)


def main():
    parser = argparse.ArgumentParser(
        description="樂活五線譜：計算股價趨勢線與 ±1/±2 標準差價位，支援多期間比較",
        epilog="不帶參數執行可進入互動選單。範例：wuxianpu.py 0050 -y 1 3.5 5 --open")
    parser.add_argument("ticker", nargs="?", help="股票代碼（台股可直接輸入數字，如 0050）")
    parser.add_argument("-y", "--years", type=float, nargs="+", metavar="N",
                        help="回歸年限，可給多個（如 -y 1 3.5 5）")
    parser.add_argument("-e", "--end", help="基準日 YYYY-MM-DD，預設今天")
    parser.add_argument("-o", "--output", help="輸出檔名（不含副檔名）")
    parser.add_argument("-f", "--format", choices=["html", "png", "both"], default="html",
                        help="圖表格式，預設 html（互動式）")
    parser.add_argument("--open", action="store_true", help="產生後自動開啟（macOS）")
    parser.add_argument("--live", action="store_true",
                        help="納入未收盤的盤中即時價（預設排除，只用已定案收盤價）")
    parser.add_argument("--no-chart", action="store_true", help="只輸出數字，不畫圖")
    args = parser.parse_args()

    end = dt.date.fromisoformat(args.end) if args.end else dt.date.today()
    interactive = not args.ticker

    # 命令列已給齊參數 → 直接跑一次
    if args.ticker and args.years:
        run(args.ticker, sorted(set(args.years)), args, end)
        return

    # 否則進入互動選單（可連續分析多檔）
    print("\n  ╭─────────────────────────────╮")
    print("  │   樂活五線譜　股價位階分析   │")
    print("  ╰─────────────────────────────╯")

    while True:
        ticker = args.ticker or choose_ticker()
        years_list = sorted(set(args.years)) if args.years else sorted(set(choose_years()))
        try:
            run(ticker, years_list, args, end)
        except SystemExit as exc:
            print(f"\n  ✗ {exc}\n")

        if not interactive:
            return
        args.ticker = args.output = None      # 下一輪重新詢問、避免覆蓋檔名
        if ask("  再分析一檔？(Enter 繼續／q 結束)：").lower() in ("q", "quit", "n"):
            print("  結束。\n")
            return


if __name__ == "__main__":
    sys.exit(main())
