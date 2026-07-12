# Component Supply Radar

Component Supply Radar 是一套給 Windows 使用者執行的電子零件供應觀測工具。它每天透過 Future Electronics 官方 API 查詢指定製造商料號（MPN）的價格、庫存與交期，把允許保存的歷史資料寫入本機 DuckDB，計算可解釋的供應壓力，並產生 HTML 與 CSV 報告。

這不是繞過網站限制的網頁爬蟲。Future Electronics 是唯一自動化供應商來源；第一版不包含 Mouser 自動收集、不包含網頁爬取、不包含 Supabase 或網頁後端。

本工具只供供應鏈研究使用，不提供投資建議、報酬預測、股票買賣訊號或自動下單。Future 單一通路的變化也不能代表整個半導體市場。

程式碼 repository 是公開的，任何人都能閱讀與下載；真實料號、API key 與歷史資料仍是私有資料，不會提交到 GitHub。公開程式碼不代表供應商資料或 API 回應可以任意轉載，實際保存與分享權仍以使用者和 Future Electronics 的授權條款為準。

## 給第一次使用的人：最短操作流程

如果你只是收到這個專案、想讓它在 Windows 電腦每天自動收集資料，先照以下步驟做即可。後面的章節是各步驟的完整說明與疑難排解。

### 第一步：把專案放在固定位置

從公開 GitHub repository 下載 ZIP 並解壓縮，或用 Git 下載。建議放在例如：

```text
C:\Users\你的帳號\Documents\component-supply-radar
```

安裝排程後不要移動這個資料夾。若必須移動，請先移除排程，移動完成後再重新安裝排程。

### 第二步：執行一鍵安裝

在專案資料夾空白處按右鍵，選擇「在終端機中開啟」，確認目前是 PowerShell，然後貼上：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

安裝器會自動準備 `uv`、Python 3.12、隔離環境、所有固定版本相依套件、DuckDB、資料夾及離線測試報告。使用者不需要自己安裝 Python 套件。

### 第三步：填入 Future API key

```powershell
notepad .\.env
```

把 Future 核發的 key 填在等號後面：

```dotenv
FUTURE_API_KEY=貼上你的正式金鑰
```

取得正式 Future 資料前必須完成這一步。沒有 key 時程式不會連線抓 Future 資料，但仍能執行離線示範與查看安裝測試報告。

### 第四步：填入要追蹤的料號

```powershell
notepad .\data\watchlist.csv
```

保留第一列欄位名稱，把下面的示範料號換成自己的 MPN。建議先放 5–20 個有效料號，確認能取得資料後再逐步增加。

### 第五步：手動跑第一次

```powershell
.\scripts\run_daily.ps1
.\scripts\open_latest_report.ps1
```

第一個指令會收集、分析、產生報告及建立到期備份；第二個指令會開啟最新 HTML 報告。第一次只有一天資料時，30 日變化顯示「資料不足」是正常結果。

### 第六步：確認成功後安裝每日排程

```powershell
.\scripts\install_scheduled_task.ps1
.\scripts\scheduled_task_status.ps1
```

預設每天 07:30 執行。安裝排程後不需要每天手動開啟程式，但該 Windows 使用者必須登入，工作才會以使用者權限執行。

### 安裝成功的判斷方式

完成後應看到：

- `data\radar.duckdb`：正式歷史資料庫。
- `data\watchlist.csv`：自己的追蹤料號。
- `work\install-check-report\latest.html`：不需要 API key 的安裝測試報告。
- `reports\latest.html`：第一次正式每日流程產生的報告。
- `data\logs\daily-output.log`：每日流程紀錄。

若只想先確認安裝、不想立刻設定 API，可執行：

```powershell
Start-Process .\work\install-check-report\latest.html
```

## 功能概要

- 每日查詢自己設定的 300–1,000 個 MPN，不下載完整商品目錄。
- 保存價格級距、可售庫存、工廠庫存、在途量、交期與收集狀態。
- 以 DuckDB 累積可重現的本機歷史。
- 計算庫存下降、價格上漲、交期拉長及缺貨廣度。
- 產生可直接開啟的 HTML 摘要和 UTF-8 CSV。
- 使用 Windows 工作排程器每天自動執行。
- 每週建立 Parquet 備份，只保留最近 12 份完整快照。
- 選擇性把獲准分享的資料單向同步到私人 MotherDuck。

## 正式支援環境

- 原生 Windows 10 或 Windows 11，非 WSL。
- Windows PowerShell 5.1 以上。
- 可連線下載安裝工具與 Python 套件。
- 約 2 GB 可用空間作為初始安裝與資料成長空間。
- 選用：Future Electronics Product Info API key。
- 選用：MotherDuck 帳號與 token。

使用者不需要預先安裝 Python。安裝腳本會透過 `uv` 準備 Python 3.12 與隔離的 `.venv`。

## 取得私人專案

這是公開 GitHub repository，不需要先取得 repository 存取權即可下載。若要回報問題或提交修改，才需要 GitHub 帳號。

已安裝 Git 的使用者，可在 PowerShell 執行：

```powershell
git clone https://github.com/kiki830621/component-supply-radar.git
Set-Location .\component-supply-radar
```

沒有 Git 時，可在 GitHub repository 頁面選擇 **Code → Download ZIP**，解壓縮後用 PowerShell 切換到該資料夾。專案安裝後請不要任意移動資料夾，否則 Windows 工作排程內的路徑會失效；若要移動，請先移除排程，移動後再重新安裝排程。

## 快速安裝

在專案根目錄開啟一般權限的 PowerShell，不需要「以系統管理員身分執行」。

先預覽安裝會做什麼：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -WhatIf
```

正式安裝：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

安裝器會依序：

1. 確認專案檔案完整。
2. 找不到 `uv` 時，嘗試用 `winget` 安裝。
3. 安裝或確認 Python 3.12。
4. 執行 `uv sync --frozen --no-dev`，完全依照 `uv.lock` 安裝正式環境相依套件。
5. 只在不存在時，從 `.env.example` 建立 `.env`。
6. 只在不存在時，從範例建立 `data\watchlist.csv`。
7. 建立資料、備份、日誌、報告及暫存資料夾。
8. 初始化正式資料庫 `data\radar.duckdb`。
9. 使用公開範例資料執行離線匯入、分析及報告自我檢查。

安裝器可以重複執行。它會保留既有 `.env`、`data\watchlist.csv`、DuckDB、報告、備份與日誌，不會刪除資料。

若電腦沒有 `winget`，請依 [uv 官方 Windows 安裝說明](https://docs.astral.sh/uv/getting-started/installation/)先安裝 `uv`，再重跑安裝器。

### 安裝完成驗證

```powershell
uv run component-supply-radar --help
Test-Path .\data\radar.duckdb
Test-Path .\work\install-check-report\latest.html
```

最後兩行都應顯示 `True`。可開啟離線自我檢查報告：

```powershell
Start-Process .\work\install-check-report\latest.html
```

## 資料與設定放在哪裡

本機資料都放在 repository 資料夾內，方便備份與移交：

| 路徑 | 用途 | 是否提交 Git |
|---|---|---|
| `.env` | Future API key、MotherDuck token 與環境設定 | 否 |
| `data\watchlist.csv` | 真正要追蹤的 MPN 清單 | 否 |
| `data\radar.duckdb` | 唯一可寫入的主要歷史資料庫 | 否 |
| `data\backups\` | 最近 12 份 Parquet 完整快照 | 否 |
| `data\logs\` | Windows 每日流程輸出與錯誤日誌 | 否 |
| `reports\` | 正式 HTML 與 CSV 報告 | 否 |
| `work\` | 安裝自我檢查及其他可丟棄的暫存檔 | 否 |
| `.venv\` | `uv` 管理的 Python 隔離環境 | 否 |

MotherDuck 的預設遠端資料庫名稱是 `component_supply_radar`。它只是選擇性查詢副本；`data\radar.duckdb` 才是本機權威來源。

## 申請及設定 Future Electronics API

官方資源：

- [Future API Solutions](https://www.futureelectronics.com/fr/api-solutions)
- [Future Product Info API Guide](https://media.futureelectronics.com/doc/Future-Electronics-API-Guide.pdf)

Future 官方表示 API 對客戶免費，實際資格、流量與保存權仍以核發時的合約或書面回覆為準。建議請 Future 業務書面確認允許：

- 每日保存指定 MPN 的價格、區域庫存及交期。
- 在私人 DuckDB 與 MotherDuck 建立歷史。
- 讓指定內部成員查詢資料。
- 計算及保存衍生的分類壓力指標。

用記事本開啟專案根目錄的 `.env`：

```powershell
notepad .\.env
```

填入核發的金鑰，等號兩側不要加引號：

```dotenv
FUTURE_API_KEY=your-issued-key
MOTHERDUCK_TOKEN=
MOTHERDUCK_DATABASE=component_supply_radar
RADAR_DATABASE=data/radar.duckdb
RADAR_TIMEZONE=Asia/Taipei
```

`.env` 已由 Git 忽略。不要把金鑰貼到 README、watchlist、問題回報、螢幕截圖或 PowerShell 指令參數。

## 設定追蹤料號

安裝器會建立 `data\watchlist.csv`。可用 Excel 編輯，但儲存時應維持 CSV 格式及原本欄位名稱。

必要欄位：

| 欄位 | 說明 |
|---|---|
| `mpn` | 製造商料號 |
| `manufacturer` | 製造商名稱 |
| `supplier_category` | Future 原始分類或目前已知分類 |
| `canonical_category` | 內部穩定分類 |
| `taxonomy_version` | 分類對照版本，例如 `v1` |
| `panel_version` | 觀察料號池版本，例如 `2026q3` |
| `role` | `core` 或 `exploratory` |
| `active` | `true` 或 `false` |

`core` 會進入正式分類指數；`exploratory` 只保存供研究，不改變正式指數。更換核心料號時應建立新的 `panel_version`，避免換樣扭曲歷史。

先以少量確定有效的 MPN 測試，再逐步增加。單次 Future 批次最多 300 個 MPN，程式會自動分批。不要把真實或商業敏感 watchlist 放進 `config\` 或提交到 Git。

## 第一次手動執行

初始化正式資料庫：

```powershell
uv run component-supply-radar init-db
```

使用 `data\watchlist.csv` 收集一次 Future 資料：

```powershell
uv run component-supply-radar collect-future --watchlist .\data\watchlist.csv
```

分析並產生報告：

```powershell
uv run component-supply-radar analyze
uv run component-supply-radar report --output .\reports
.\scripts\open_latest_report.ps1
```

第一次只有一筆歷史時，30 日比較會顯示資料不足，這是正常情況，不代表零壓力。

若尚未取得 API key，可先使用不連線的範例 CSV：

```powershell
uv run component-supply-radar --database .\work\demo.duckdb init-db
uv run component-supply-radar --database .\work\demo.duckdb import-csv .\examples\supplier-observations.csv
uv run component-supply-radar --database .\work\demo.duckdb analyze
uv run component-supply-radar --database .\work\demo.duckdb report --output .\work\demo-report
Start-Process .\work\demo-report\latest.html
```

## 每日執行

先手動測試完整每日流程：

```powershell
.\scripts\run_daily.ps1
```

這個腳本會使用 `data\watchlist.csv`，依序執行 Future 收集、分析、報告、選擇性 MotherDuck 同步及到期備份。未設定 Future API key 時會略過網路收集，仍可完成本機分析與報告。

輸出追加至：

- `data\logs\daily-output.log`
- `data\logs\daily-error.log`

## 安裝 Windows 每日工作排程

預覽每天 07:30 的排程：

```powershell
.\scripts\install_scheduled_task.ps1 -WhatIf
```

正式建立或更新：

```powershell
.\scripts\install_scheduled_task.ps1
```

自訂時間，例如每天 08:15：

```powershell
.\scripts\install_scheduled_task.ps1 -At "08:15"
```

查詢狀態、上次結果及下次執行時間：

```powershell
.\scripts\scheduled_task_status.ps1
```

立即手動觸發已安裝的工作：

```powershell
Start-ScheduledTask -TaskName "ComponentSupplyRadar-Daily"
```

移除排程但保留程式和所有資料：

```powershell
.\scripts\uninstall_scheduled_task.ps1 -WhatIf
.\scripts\uninstall_scheduled_task.ps1
```

排程以目前登入的 Windows 使用者執行，不把 Windows 密碼存入工作定義。使用者必須登入，工作才能以互動式使用者權限執行。

## MotherDuck 分享

建立私人 MotherDuck 資料庫與 token 後，在 `.env` 填入：

```dotenv
MOTHERDUCK_TOKEN=your-private-token
MOTHERDUCK_DATABASE=component_supply_radar
```

手動同步：

```powershell
uv run component-supply-radar sync
```

同步是單向的：本機 DuckDB 是唯一可寫入的權威來源，MotherDuck 是供指定使用者查詢的副本。只有來源政策中 `cloud_share_allowed = true` 的資料會同步。沒有 token 時會安全略過；遠端失敗不會修改本機資料。

## 備份與容量

手動建立 Parquet 備份：

```powershell
uv run component-supply-radar backup --output .\data\backups
```

每份快照含所有本機資料表、`manifest.json`、schema version 與 UTC 匯出時間。系統只保留最近 12 份完成快照。

建議定期把整個 `data\backups\` 複製到另一顆硬碟或有權限控管的私人雲端。Parquet 是災難復原與資料交換格式；正式操作仍以 `data\radar.duckdb` 為主。

每日追蹤約 1,000 個 MPN 時，標準化資料、價格級距和備份估計每年約 1–3 GB，實際大小取決於 offer 數量與價格級距。本專案不下載 datasheet、圖片或完整目錄。

## 更新程式

### 使用 Git 取得的專案

先停止正在執行的每日工作並建立備份：

```powershell
uv run component-supply-radar backup --output .\data\backups
git pull --ff-only
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

重新執行安裝器會更新相依套件及資料結構，但保留 `.env`、watchlist 與既有資料。

### 使用 ZIP 取得的專案

1. 先備份舊資料夾的 `.env`、`data\` 與必要的 `reports\`。
2. 下載並解壓縮新版 ZIP 到新資料夾。
3. 把 `.env` 與 `data\` 複製到新版資料夾。
4. 在新版資料夾執行 `install.ps1`。
5. 若曾安裝排程，在新版資料夾重新執行 `install_scheduled_task.ps1`。

不要直接覆蓋或刪除唯一一份 `data\radar.duckdb`。

## 解除安裝

先移除 Windows 工作排程：

```powershell
.\scripts\uninstall_scheduled_task.ps1
```

這個腳本不會刪除資料。確認已另行保存 `.env`、`data\` 與需要的報告後，才手動刪除整個 repository 資料夾。

`uv` 和 uv 管理的 Python 可能被其他專案共用，除非確定不再使用，否則不必解除安裝。uv 的移除方式請參考 [官方安裝文件](https://docs.astral.sh/uv/getting-started/installation/#uninstallation)。

## 壓力指標

料號壓力由四個透明元件組成：

- 30 日庫存跌幅：最多 35 分。
- 30 日交期增加：最多 25 分。
- 可比較價格上漲：最多 25 分。
- 缺貨廣度：最多 15 分。

分類強度取有效核心料號分數中位數；廣度是超過 60 分的核心料號比例。警訊狀態包括 `normal`、`watch`、`confirmed`、`recovering` 與 `unknown`。樣本不足或收集失敗會標示為 `unknown`，不會被寫成零庫存或零壓力。

## CLI 指令

```text
init-db         初始化或更新 DuckDB schema
import-csv      匯入已獲授權的 CSV
collect-future  收集 Future 指定料號
analyze         更新分類壓力與警訊
report          產生 HTML 與 CSV
sync            單向同步 MotherDuck
backup          建立 Parquet 快照
run-daily       執行每日本機流程
```

自訂資料庫時，`--database` 必須放在子指令前：

```powershell
uv run component-supply-radar --database .\data\radar.duckdb --help
```

## 常見問題

- **PowerShell 阻擋腳本**：安裝時使用 README 的 `powershell -ExecutionPolicy Bypass -File ...`。日常腳本若仍被政策阻擋，也可以相同方式執行指定檔案；不必永久降低整台電腦的執行政策。
- **找不到 `uv`**：關閉 PowerShell 後重新開啟，再重跑安裝器；仍失敗時依 uv 官方 Windows 說明安裝。
- **缺少 `FUTURE_API_KEY`**：用 `notepad .\.env` 檢查值不是空白，儲存後重跑。
- **Future 401／402／403／406**：API key、試用或組織授權有問題；聯絡 Future 業務，不要反覆重試。
- **Future 429 或 5xx**：程式會有限次重試；持續發生時查看 `data\logs\daily-error.log`，稍後再執行。
- **報告顯示資料不足**：同一核心 MPN 至少需要兩筆可比較歷史；30 日比較要等較早觀測累積。
- **找不到 `data\watchlist.csv`**：重跑 `install.ps1`；既有 watchlist 不會被覆寫。
- **工作排程沒有執行**：確認專案資料夾沒有移動、Windows 使用者已登入，再執行 `scheduled_task_status.ps1` 並查看日誌。
- **MotherDuck 同步失敗**：本機資料不受影響；確認 token、資料庫名稱與網路後重跑 `sync`。
- **DuckDB 被鎖定**：同一時間只允許一個寫入流程，關閉其他使用該資料庫的程式後重試。

## 開發與驗證

開發環境安裝所有相依套件：

```powershell
uv sync --frozen --all-groups
```

完整品質檢查：

```powershell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run component-supply-radar --help
```

`.github\workflows\ci.yml` 會在乾淨的 `windows-latest` GitHub Actions runner 重做 frozen 安裝、PowerShell 剖析、完整測試與離線 quickstart。正式 API 與 MotherDuck 不會在 CI 呼叫，也不需要設定 secrets。

## 授權

本專案的程式碼與 repository 內文件依 [MIT License](LICENSE) 授權。

```text
Copyright (c) 2026 kiki830621
```

MIT License 允許使用、複製、修改、合併、發布與散布，但必須保留原始著作權及授權聲明，且軟體不提供任何明示或默示擔保。

此授權只適用於本 repository 的程式碼與文件，不會改變 Future Electronics API、供應商資料、使用者 API key、真實 watchlist 或歷史資料的權利。這些內容仍受各自合約、授權條款及資料所有權限制。

## 參考資料

- [Future Market Conditions Report](https://media.futureelectronics.com/doc/Market-Conditions-Report.pdf)
- [Future API Solutions](https://www.futureelectronics.com/fr/api-solutions)
- [uv Windows 安裝](https://docs.astral.sh/uv/getting-started/installation/)
- [Microsoft Windows 工作排程器](https://learn.microsoft.com/en-us/windows/win32/taskschd/schtasks)
- [ECIA](https://www.ecianow.org/)
- [Semiconductor Industry Association](https://www.semiconductors.org/)
- [SEMI](https://www.semi.org/)
- [WSTS](https://www.wsts.org/)
- [TTI MarketEye](https://www.tti.com/content/ttiinc/en/resources/marketeye.html)

外部報告只保存網址、日期與合法人工筆記；本專案不大量重製受著作權保護的內容。
