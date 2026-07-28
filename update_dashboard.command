#!/bin/zsh
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

AUTO_PUSH="${AUTO_PUSH:-false}"

if ! python3 scripts/build_dashboard_data.py; then
  echo "エラー: ダッシュボードデータの更新に失敗しました"
  read -r "?Enterキーで閉じます"
  exit 1
fi

echo "ダッシュボードデータを更新しました"

if [[ "$AUTO_PUSH" == "true" ]]; then
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git add web/dashboard_data.json
    if git diff --cached --quiet; then
      echo "Gitにコミットする変更はありません"
    else
      git commit -m "Update dashboard data"
      git push
    fi
  else
    echo "Gitリポジトリではないため、自動pushをスキップしました"
  fi
else
  echo "自動pushはOFFです（AUTO_PUSH=true で有効化）"
fi

read -r "?Enterキーで閉じます"
