#!/usr/bin/env python3
"""
樂活五線譜 GUI
------------------------------------------------
本機網頁介面。執行後自動開啟瀏覽器，提供股票代碼與回歸年限的輸入欄位。

啟動：
    python3 wuxianpu_gui.py            # 自動開瀏覽器
    python3 wuxianpu_gui.py --port 880 # 指定連接埠
    python3 wuxianpu_gui.py --no-open  # 不自動開啟

相依：僅需 numpy（與 wuxianpu.py 相同），GUI 本身使用 Python 標準函式庫，
      不需 Flask / Streamlit 等任何額外套件。
本服務僅綁定 127.0.0.1（本機），不對外開放。
"""

import argparse
import datetime as dt
import html as html_mod
import http.server
import socketserver
import threading
import traceback
import sys
import urllib.parse
import webbrowser

MIN_PYTHON = (3, 8)
if sys.version_info < MIN_PYTHON:
    raise SystemExit(
        f"需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} 以上，"
        f"目前為 {sys.version_info[0]}.{sys.version_info[1]}。\n"
        f"請至 https://www.python.org/downloads/ 安裝新版。")

import wuxianpu as core

PRESET_YEARS = [1.0, 3.5, 5.0, 10.0]

PAGE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>樂活五線譜</title>
<style>
  :root { --bg:#f6f7f9; --panel:#fff; --fg:#1a1a1a; --muted:#6b7280;
          --line:#e5e7eb; --accent:#1a1a1a; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#101115; --panel:#1b1d23; --fg:#e9e9ee; --muted:#9aa0ac;
            --line:#2c2f37; --accent:#e9e9ee; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font-size:14px;
         font-family:-apple-system,"PingFang TC","Noto Sans TC","Microsoft JhengHei",sans-serif; }
  .top { background:var(--panel); border-bottom:1px solid var(--line); padding:16px 22px; }
  .inner { max-width:1240px; margin:0 auto; }
  h1 { font-size:17px; margin:0 0 14px; font-weight:600; letter-spacing:.3px; }
  form { display:flex; gap:22px; flex-wrap:wrap; align-items:flex-end; }
  .fld { display:flex; flex-direction:column; gap:6px; }
  label { font-size:12px; color:var(--muted); font-weight:500; }
  input[type=text], input[type=date] {
    background:var(--bg); border:1px solid var(--line); color:var(--fg);
    border-radius:8px; padding:9px 11px; font-size:14px; font-family:inherit; }
  input[type=text]:focus, input[type=date]:focus { outline:2px solid #6b7280; outline-offset:1px; }
  #ticker { width:190px; font-weight:600; letter-spacing:.5px; }
  #custom { width:170px; }
  .chips { display:flex; gap:7px; }
  .chip input { display:none; }
  .chip span { display:block; border:1px solid var(--line); background:var(--bg);
     border-radius:8px; padding:9px 15px; cursor:pointer; user-select:none; font-size:13.5px; }
  .chip input:checked + span { background:var(--accent); color:var(--bg); border-color:var(--accent);
     font-weight:600; }
  .opt { display:flex; align-items:center; gap:7px; font-size:13px; color:var(--muted);
         padding-bottom:10px; cursor:pointer; }
  button { background:var(--accent); color:var(--bg); border:0; border-radius:8px;
     padding:10px 26px; font-size:14px; font-weight:600; cursor:pointer; font-family:inherit; }
  button:active { opacity:.75; }
  .quit { position:absolute; top:18px; right:24px; font-size:12.5px; color:var(--muted);
     text-decoration:none; border:1px solid var(--line); border-radius:999px; padding:5px 13px; }
  .quit:hover { color:#b91c1c; border-color:#b91c1c; }
  .top { position:relative; }
  .presets { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; font-size:12.5px; }
  .presets a { color:var(--muted); text-decoration:none; border:1px solid var(--line);
     border-radius:999px; padding:4px 12px; background:var(--panel); }
  .presets a:hover { color:var(--fg); border-color:var(--muted); }
  .body { max-width:1240px; margin:0 auto; padding:18px 22px 40px; }
  .msg { background:#fee2e2; color:#991b1b; border-radius:10px; padding:14px 18px; }
  @media (prefers-color-scheme: dark) { .msg { background:#3b1616; color:#fca5a5; } }
  .hint { color:var(--muted); padding:40px 4px; line-height:1.9; }
  iframe { width:100%; border:0; background:var(--panel); border-radius:12px;
           border:1px solid var(--line); }
  .spin { display:none; color:var(--muted); font-size:13px; padding-bottom:11px; }
  form.busy .spin { display:block; }
</style>
</head>
<body>
<div class="top"><div class="inner">
  <h1>樂活五線譜　股價位階分析</h1>
  <form method="get" action="/" onsubmit="this.classList.add('busy')">
    <div class="fld">
      <label for="ticker">股票代碼</label>
      <input type="text" id="ticker" name="ticker" value="__TICKER__" list="tk"
             placeholder="0050 / 2330 / AAPL" autocomplete="off" required>
      <datalist id="tk">__DATALIST__</datalist>
    </div>
    <div class="fld">
      <label>回歸年限（可複選）</label>
      <div class="chips">__CHIPS__</div>
    </div>
    <div class="fld">
      <label for="custom">自行輸入年限</label>
      <input type="text" id="custom" name="custom" value="__CUSTOM__"
             placeholder="例：0.5 2 7.5" autocomplete="off">
    </div>
    <div class="fld">
      <label for="end">基準日</label>
      <input type="date" id="end" name="end" value="__END__">
    </div>
    <label class="opt"><input type="checkbox" name="live" value="1" __LIVE__>納入盤中未收盤價</label>
    <div class="spin">分析中…</div>
    <button type="submit">分析</button>
  </form>
  <a class="quit" href="/quit" title="關閉伺服器並結束程式">結束程式</a>
  <div class="presets">__PRESETS__</div>
</div></div>
<div class="body">__RESULT__</div>
</body>
</html>
"""


def render_page(params, result):
    """組出主頁面 HTML。"""
    ticker = params.get("ticker", "")
    custom = params.get("custom", "")
    end = params.get("end", "")
    chosen = params.get("years", set())

    chips = "".join(
        f'<label class="chip"><input type="checkbox" name="years" value="{y:g}"'
        f'{" checked" if y in chosen else ""}><span>{y:g} 年</span></label>'
        for y in PRESET_YEARS)

    datalist = "".join(f'<option value="{c}">{n}</option>'
                       for c, n in core.PRESET_TICKERS)

    presets = "".join(
        f'<a href="/?ticker={urllib.parse.quote(c)}&years=1&years=3.5&years=5&years=10">'
        f'{html_mod.escape(n)}</a>' for c, n in core.PRESET_TICKERS)

    return (PAGE
            .replace("__TICKER__", html_mod.escape(ticker, quote=True))
            .replace("__CUSTOM__", html_mod.escape(custom, quote=True))
            .replace("__END__", html_mod.escape(end, quote=True))
            .replace("__LIVE__", "checked" if params.get("live") else "")
            .replace("__CHIPS__", chips)
            .replace("__DATALIST__", datalist)
            .replace("__PRESETS__", presets)
            .replace("__RESULT__", result))


def parse_params(query: str) -> dict:
    """解析查詢字串，回傳正規化後的參數。"""
    raw = urllib.parse.parse_qs(query)
    years = set()
    for value in raw.get("years", []):
        try:
            years.add(float(value))
        except ValueError:
            pass
    return {
        "ticker": (raw.get("ticker", [""])[0]).strip(),
        "custom": (raw.get("custom", [""])[0]).strip(),
        "end": (raw.get("end", [""])[0]).strip(),
        "live": bool(raw.get("live")),
        "years": years,
    }


def resolve_years(params) -> list:
    """合併勾選與自訂年限。"""
    years = set(params["years"])
    if params["custom"]:
        years.update(core.parse_years(params["custom"]))   # 格式錯誤會拋 ValueError
    return sorted(years) or [3.5]


def analyze_request(params):
    """執行分析，回傳 (圖表 HTML, 提示訊息)。"""
    years_list = resolve_years(params)
    end = dt.date.fromisoformat(params["end"]) if params["end"] else dt.date.today()
    # 需涵蓋最長迴歸年限與最長均線（十年線 2400 個交易日 ≈ 10 年）
    span = max(max(years_list), 10.5)
    start = end - dt.timedelta(days=round(365.25 * span) + 10)

    code, name, rows, intraday = core.resolve(params["ticker"], start, end)

    note = ""
    if intraday and not params["live"]:
        rows = [r for r in rows if r[0] != intraday["date"]]
        if not rows:
            raise ValueError("排除盤中資料後已無可用資料，請勾選「納入盤中未收盤價」。")
        note = (f'已排除 {intraday["date"]} 盤中未收盤資料'
                f'（現價 {intraday["price"]:,.2f}，{intraday["close_time"]} 收盤）')
        end = rows[-1][0]
        intraday = None

    periods = [core.analyze(rows, y, end) for y in years_list]
    mas = core.moving_averages(rows)
    chart = core.build_html(code, name, periods, end, intraday, mas)
    return chart, note


class Handler(http.server.BaseHTTPRequestHandler):
    """單頁應用：/ 顯示表單與結果，/chart 提供內嵌的圖表頁。"""

    charts = {}          # 以 token 暫存最近產生的圖表 HTML
    lock = threading.Lock()
    server_ref = None    # 供 /quit 關閉伺服器用

    def log_message(self, *_):          # 關閉預設的逐筆請求日誌
        pass

    def send_html(self, body: str, status: int = 200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/quit":
            self.send_html(
                '<!DOCTYPE html><html lang="zh-TW"><head><meta charset="utf-8">'
                '<title>已結束</title><style>body{font-family:-apple-system,'
                '"PingFang TC",sans-serif;display:flex;align-items:center;'
                'justify-content:center;height:100vh;margin:0;color:#374151;'
                'background:#f6f7f9}div{text-align:center;line-height:1.9}'
                '@media(prefers-color-scheme:dark){body{background:#101115;color:#9aa0ac}}'
                '</style></head><body><div><h2>樂活五線譜已結束</h2>'
                '<p>可以關閉這個分頁了。<br>要再次使用，重新開啟 App 即可。</p>'
                '</div></body></html>')
            if Handler.server_ref:      # 回應送出後才關閉，避免瀏覽器收到中斷
                threading.Timer(0.4, Handler.server_ref.shutdown).start()
            return

        if parsed.path == "/chart":
            token = urllib.parse.parse_qs(parsed.query).get("t", [""])[0]
            with Handler.lock:
                chart = Handler.charts.get(token)
            if chart is None:
                self.send_html("<p>圖表已過期，請重新分析。</p>", 404)
            else:
                self.send_html(chart)
            return

        if parsed.path not in ("/", "/index.html"):
            self.send_html("<p>Not Found</p>", 404)
            return

        params = parse_params(parsed.query)

        if not params["ticker"]:
            hint = ('<div class="hint">輸入股票代碼並選擇回歸年限，按「分析」開始。<br>'
                    '台股輸入數字即可（自動判斷上市／上櫃），美股輸入代碼如 AAPL、NVDA。<br>'
                    '預設僅使用已收盤的價格；盤中想看即時位階請勾選上方選項。</div>')
            self.send_html(render_page(params, hint))
            return

        try:
            chart, note = analyze_request(params)
        except ValueError as exc:
            self.send_html(render_page(params, f'<div class="msg">{html_mod.escape(str(exc))}</div>'))
            return
        except SystemExit as exc:
            self.send_html(render_page(params, f'<div class="msg">{html_mod.escape(str(exc))}</div>'))
            return
        except Exception:                                   # noqa: BLE001
            traceback.print_exc()
            self.send_html(render_page(
                params, '<div class="msg">分析失敗，請確認股票代碼是否正確，或稍後再試。</div>'))
            return

        token = str(abs(hash((params["ticker"], parsed.query, dt.datetime.now()))))[:12]
        with Handler.lock:
            Handler.charts[token] = chart
            if len(Handler.charts) > 20:                    # 僅保留最近 20 份
                for key in list(Handler.charts)[:-20]:
                    Handler.charts.pop(key, None)

        banner = (f'<div class="msg" style="background:#e0f2fe;color:#075985;'
                  f'margin-bottom:14px">{html_mod.escape(note)}</div>') if note else ""
        body = (banner +
                f'<iframe src="/chart?t={token}" id="fr" '
                f'onload="this.style.height=this.contentWindow.document.body.scrollHeight+40+\'px\'">'
                f'</iframe>')
        self.send_html(render_page(params, body))


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(description="樂活五線譜 本機網頁介面")
    parser.add_argument("-p", "--port", type=int, default=8765, help="連接埠，預設 8765")
    parser.add_argument("--no-open", action="store_true", help="不自動開啟瀏覽器")
    args = parser.parse_args()

    # 連接埠被佔用時自動往上找可用的，避免重複啟動時失敗
    httpd = None
    for offset in range(20):
        try:
            httpd = Server(("127.0.0.1", args.port + offset), Handler)
            break
        except OSError:
            continue
    if httpd is None:
        raise SystemExit(f"連接埠 {args.port}~{args.port + 19} 都被佔用，"
                         f"請用 --port 指定其他號碼。")

    Handler.server_ref = httpd

    with httpd:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/"
        print(f"\n  樂活五線譜 GUI 已啟動 → {url}")
        print("  按 Ctrl+C 結束\n")
        if not args.no_open:
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  已結束。\n")


if __name__ == "__main__":
    main()
