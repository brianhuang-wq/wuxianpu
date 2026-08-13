# 樂活五線譜

股價位階分析工具。以線性迴歸求出趨勢線，再用殘差標準差畫出 ±1σ、±2σ 共五條線，
判斷目前股價落在長期趨勢的偏高或偏低區域，並與月線至十年線一併排序比較。

網頁版全部運算都在瀏覽器完成，手機、平板、電腦開網址即可使用。

---

## 一、放上 GitHub Pages（手機也能用）

### 最快的方式：執行 `上傳到GitHub.command`

雙擊它，腳本會自動完成建立 repo、上傳、開啟 Pages、設定 Actions 權限，
你只需要在瀏覽器完成一次 GitHub 授權。需要先安裝
[GitHub CLI](https://cli.github.com)（腳本會偵測並引導）。

授權由 GitHub 官方工具處理，腳本不會接觸你的密碼或權杖。

如果偏好手動操作，或腳本執行不順，請照下面的步驟做。

### 1. 建立 repo

1. 登入 GitHub，右上角 **＋ → New repository**
2. Repository name 隨意（例如 `wuxianpu`）
3. 選 **Public**（Public 才能免費用 GitHub Pages）
4. 點 **Create repository**

### 2. 上傳檔案

在新 repo 頁面點 **Add file → Upload files**，把這個資料夾裡的所有東西拖進去
（含 `.github` 資料夾；若瀏覽器不讓你拖資料夾，可改用 GitHub Desktop）。
拖好後在下方點 **Commit changes**。

### 3. 開啟 GitHub Pages

1. 進入 repo 的 **Settings → Pages**
2. Source 選 **Deploy from a branch**
3. Branch 選 **main**，資料夾選 **/docs**，按 **Save**
4. 等一兩分鐘，頁面上方會出現你的網址：
   `https://<你的帳號>.github.io/<repo 名稱>/`

用手機打開那個網址就能用了。

### 4. 加到手機主畫面（像 App 一樣）

- **iPhone（Safari）**：點下方分享鈕 → 加入主畫面
- **Android（Chrome）**：點右上角 ⋮ → 安裝應用程式／加到主畫面

之後從主畫面開啟會是全螢幕，沒有瀏覽器網址列。

---

## 二、自動更新股價

`.github/workflows/update-data.yml` 已設定好排程，會自動抓最新收盤價並更新網頁：

- 每個工作日 **台北時間 14:20**（台股 13:30 收盤後）
- 每個工作日 **台北時間隔日 05:30**（美股收盤後）

第一次上傳後，建議先手動跑一次確認正常：
進入 **Actions → 更新股價資料 → Run workflow**。

> 若 Actions 頁面顯示需要啟用，點 **I understand my workflows, go ahead and enable them**。
> 若推送失敗，到 **Settings → Actions → General → Workflow permissions**，
> 改成 **Read and write permissions** 後儲存。

GitHub 的排程在流量高峰時可能延遲數十分鐘，屬正常現象。
另外 Public repo 若連續 60 天沒有任何動作，GitHub 會自動停用排程，
屆時到 Actions 頁面點一下重新啟用即可。

---

## 三、修改追蹤的股票

編輯 **`tickers.txt`**，每行一檔：

```
2412,中華電
00878,國泰永續高股息
NVDA,輝達
```

- 台股直接寫數字，上市上櫃都會自動判斷
- 美股寫代碼，指數用 `^` 開頭（`^TWII` 台股加權、`^GSPC` 標普500）
- `#` 開頭是註解

改完 commit，下次排程（或手動觸發 workflow）就會生效。
標的越多檔案越大，建議控制在 20 檔以內。

---

## 四、在電腦上使用（選用）

不想依賴 GitHub 也可以在本機跑，功能更完整（可分析任意股票、即時資料）：

```bash
pip3 install --only-binary=:all: numpy
python3 wuxianpu_gui.py        # 網頁介面
python3 wuxianpu.py            # 命令列互動選單
python3 wuxianpu.py 0050 -y 1 3.5 5 10
```

自己重新產生網頁版：

```bash
python3 gen_standalone.py --output docs/index.html --tickers tickers.txt
```

---

## 演算法

1. 取近 N 年日收盤價（未還原權息）
2. 以交易日序號為 x、收盤價為 y 跑最小平方線性迴歸，得到趨勢線
3. 計算殘差的標準差 σ
4. 五條線 = 趨勢線、±1σ、±2σ

已對照 sentimentinsideout.com 的樂活五線譜實測驗證，誤差小於 0.15。

情緒判定：現價高於 +2σ 為「極度貪婪」，+1σ~+2σ 為「貪婪」，
−1σ~+1σ 為「中性」，−2σ~−1σ 為「恐懼」，低於 −2σ 為「極度恐懼」。

---

## 注意事項

- **一律使用已收盤的價格**。盤中執行時會自動排除當日未定案的即時報價。
- **新上市標的資料不足時會顯示警告**。例如 009816 於 2026 年 2 月上市，
  跑 3.5 年回歸時實際只有約半年資料，五條線的統計意義有限。
- **回歸期間長短會大幅影響結論**。同一檔股票用 1 年與 10 年回歸，
  可能一個顯示「中性」、另一個顯示「極度貪婪」，這是正常現象，
  代表短線與長線位階背離。判讀時請留意你關心的是哪個時間尺度。
- 資料來源為 Yahoo Finance，非官方 API，可能有延遲或缺漏。
- 本工具僅為技術面數值計算，**不構成投資建議**。
