# HCバロー Web営業ダッシュボード

既存のExcel入力を利用し、PC・スマートフォンで閲覧できる静的Webダッシュボードを生成します。外部サーバーやデータベースは不要です。

## 初回設定

プロジェクトフォルダへ移動し、既存の依存パッケージを確認します。

```bash
cd /Users/oonishihiroto/Documents/SalesReportGenerator/NagoyaSalesDashboard
python3 -m pip install -r requirements.txt
```

## JSON更新方法

```bash
python3 scripts/build_dashboard_data.py
```

Macでは `update_dashboard.command` をダブルクリックしても更新できます。初期状態ではGitへの自動pushは行いません。

自動pushを有効にする場合：

```bash
AUTO_PUSH=true ./update_dashboard.command
```

## ローカル確認方法

`file://` ではブラウザの制約によりJSONを取得できないため、HTTPサーバーを使用します。

```bash
cd web
python3 -m http.server 8000
```

ブラウザで以下を開きます。

<http://localhost:8000>

## VS Code Live Server

1. VS Codeでプロジェクトを開きます。
2. Live Server拡張機能をインストールします。
3. `web/index.html` を右クリックします。
4. `Open with Live Server` を選択します。

## Cloudflare Pages公開方法

1. プロジェクトをGitHubなどのGitリポジトリへpushします。
2. Cloudflare Dashboardで `Workers & Pages` → `Create` → `Pages` を選択します。
3. 対象リポジトリを接続します。
4. ビルドコマンドは空欄、出力ディレクトリは `web` に設定します。
5. デプロイを実行します。

`web/` は静的ファイルのみで構成されているため、そのままCloudflare Pagesへ公開できます。

## 通常の更新手順

1. `input/` のExcelを差し替えます。
2. `python3 scripts/build_dashboard_data.py` または `update_dashboard.command` を実行します。
3. ローカルで表示を確認します。
4. 公開環境を利用している場合は変更をGitへpushします。

## エラー時の確認項目

- `input/` にレポートアクロスと企業別計画が存在するか
- `pandas`、`openpyxl`、`xlrd` がインストールされているか
- ローカル確認をHTTPサーバー経由で行っているか
- ブラウザの開発者ツールにJSON取得エラーが出ていないか
- `web/dashboard_data.json` がUTF-8の正しいJSONか
- Chart.js CDNへ接続できるネットワーク環境か

データが存在しない場合、生成処理は `null` または空配列を出力し、サイト自体は表示可能な状態を維持します。
