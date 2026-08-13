#!/bin/bash
# 樂活五線譜 — 一鍵上傳到 GitHub 並開啟 GitHub Pages
#
# 使用 GitHub 官方的 gh 工具，授權過程由 gh 自己在瀏覽器完成，
# 本腳本不會接觸、儲存或傳送你的密碼與權杖。

set -u
cd "$(dirname "$0")" || exit 1

echo ""
echo "  ╭────────────────────────────────────╮"
echo "  │   樂活五線譜　上傳到 GitHub        │"
echo "  ╰────────────────────────────────────╯"
echo ""

fail() { echo ""; echo "  ✗ $1"; echo ""; read -n 1 -s -r -p "  按任意鍵關閉..."; exit 1; }

# ── 1. 檢查 git ──────────────────────────────────────────────
if ! command -v git >/dev/null 2>&1; then
  echo "  需要 git，正在觸發 macOS 的開發者工具安裝…"
  xcode-select --install 2>/dev/null
  fail "請完成「命令列工具」安裝後，再執行一次本檔案。"
fi
echo "  ✓ git $(git --version | awk '{print $3}')"

# ── 2. 檢查 gh（GitHub 官方 CLI）─────────────────────────────
if ! command -v gh >/dev/null 2>&1; then
  echo ""
  echo "  ! 找不到 GitHub CLI（gh），這是上傳所需的官方工具。"
  if command -v brew >/dev/null 2>&1; then
    read -r -p "    偵測到 Homebrew，是否用它安裝 gh？(y/N) " yn
    if [[ "$yn" =~ ^[Yy]$ ]]; then
      brew install gh || fail "安裝失敗，請手動執行：brew install gh"
    else
      fail "已取消。"
    fi
  else
    echo "    請至 https://cli.github.com 下載安裝後再執行一次。"
    open "https://cli.github.com" 2>/dev/null
    fail "安裝完成後請重新執行本檔案。"
  fi
fi
echo "  ✓ gh $(gh --version | head -1 | awk '{print $3}')"

# ── 3. 登入 GitHub（瀏覽器授權，本腳本不接觸憑證）───────────
if ! gh auth status >/dev/null 2>&1; then
  echo ""
  echo "  尚未登入 GitHub，接下來會在瀏覽器開啟授權頁面。"
  echo "  （選 GitHub.com → HTTPS → 用瀏覽器登入）"
  echo ""
  gh auth login || fail "登入未完成。"
fi
ACCOUNT=$(gh api user --jq .login 2>/dev/null) || fail "無法取得帳號資訊，請重新執行 gh auth login。"
echo "  ✓ 已登入：$ACCOUNT"

# ── 4. 詢問 repo 名稱 ────────────────────────────────────────
echo ""
read -r -p "  要建立的 repo 名稱（直接 Enter = wuxianpu）：" REPO
REPO="${REPO:-wuxianpu}"
if [[ ! "$REPO" =~ ^[A-Za-z0-9._-]+$ ]]; then
  fail "名稱只能使用英數字、底線、句點與連字號。"
fi

if gh repo view "$ACCOUNT/$REPO" >/dev/null 2>&1; then
  fail "$ACCOUNT/$REPO 已經存在。請換一個名稱，或先到 GitHub 刪除舊的。"
fi

echo ""
echo "  即將建立公開 repo：$ACCOUNT/$REPO"
echo "  （公開 repo 才能免費使用 GitHub Pages；內容所有人都看得到）"
read -r -p "  確認繼續？(y/N) " yn
[[ "$yn" =~ ^[Yy]$ ]] || fail "已取消。"

# ── 5. 建立本機 git 並推送 ───────────────────────────────────
echo ""
echo "  建立 repo 並上傳中…"
if [ ! -d .git ]; then
  git init -q -b main || fail "git init 失敗。"
fi
git add -A || fail "git add 失敗。"
git -c user.name="$ACCOUNT" -c user.email="$ACCOUNT@users.noreply.github.com" \
    commit -q -m "樂活五線譜 初始版本" 2>/dev/null || echo "  （無新變更可提交）"

gh repo create "$REPO" --public --source=. --remote=origin --push \
  || fail "建立或推送失敗，請看上方訊息。"
echo "  ✓ 檔案已上傳"

# ── 6. 允許 Actions 寫入（自動更新資料需要）──────────────────
gh api --method PUT "repos/$ACCOUNT/$REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=write \
  -F can_approve_pull_request_reviews=false >/dev/null 2>&1 \
  && echo "  ✓ 已允許 Actions 寫入" \
  || echo "  ! Actions 寫入權限設定失敗，請手動至 Settings → Actions → General 調整"

# ── 7. 開啟 GitHub Pages（來源：main 分支的 /docs）───────────
sleep 2
gh api --method POST "repos/$ACCOUNT/$REPO/pages" \
  -f "source[branch]=main" -f "source[path]=/docs" >/dev/null 2>&1 \
  && echo "  ✓ 已開啟 GitHub Pages" \
  || echo "  ! Pages 自動開啟失敗，請手動至 Settings → Pages 設定（main / docs）"

# ── 8. 完成 ──────────────────────────────────────────────────
URL="https://$ACCOUNT.github.io/$REPO/"
echo ""
echo "  ────────────────────────────────────────"
echo "  完成！網址（約需 1~3 分鐘才會生效）："
echo ""
echo "    $URL"
echo ""
echo "  手機開這個網址即可使用；iPhone 用 Safari 開啟後"
echo "  點分享鈕 →「加入主畫面」就會變成 App 圖示。"
echo "  ────────────────────────────────────────"
echo ""
read -r -p "  現在開啟 repo 頁面確認狀態嗎？(Y/n) " yn
[[ "$yn" =~ ^[Nn]$ ]] || gh repo view "$ACCOUNT/$REPO" --web

echo ""
read -n 1 -s -r -p "  按任意鍵關閉..."
