## Why

電子零件價格、庫存與交期的變化可能比季度產業報告更早反映特定通路的供應壓力，但目前缺乏可持續保存、跨日比較且不把單一料號雜訊誤當成市場結論的研究工具。第一版需要以 Future Electronics 為唯一自動 API，在明確的資料授權與研究解讀界線內建立可稽核的歷史觀測。

## What Changes

- 建立 Future Electronics Product Info API 收集器，每日查詢有版本的核心與探索料號池。
- 直接保存獲准使用的區域庫存、在途量、工廠交期、價格級距與產品屬性至本機 DuckDB。
- 支援合法自有 CSV 匯入，作為離線測試、備援與補充來源。
- 同時保存供應商原始分類及內部標準分類，以支援跨來源擴充與稽核。
- 建立分類層供應壓力指數，以料號分數中位數表示強度，以惡化料號比例表示廣度，並呈現樣本覆蓋與資料不足狀態。
- 建立 `normal`、`watch`、`confirmed`、`recovering`、`unknown` 警訊狀態，避免單日波動與收集失敗造成錯誤結論。
- 將公司關聯拆成可由 MPN 證明的直接製造商曝險，以及人工整理且明確標示的主題曝險。
- 將允許分享的標準化資料單向同步至 MotherDuck，並每週輸出 Parquet 備份與 HTML／CSV 研究報告。
- 提供原生 Windows PowerShell 安裝器、目前使用者的 Windows 工作排程、離線測試與完整 README。

## Capabilities

### New Capabilities

- `source-ingestion-policy`: Future API、自有 CSV、料號池版本與來源授權政策的收集契約。
- `historical-storage`: DuckDB 歷史觀測、價格級距、執行稽核、冪等寫入與 Parquet 備份契約。
- `supply-pressure-signals`: 料號與分類壓力、樣本覆蓋及多階段警訊狀態的計算契約。
- `research-exposure-model`: 內部標準分類、直接製造商曝險與人工主題曝險的分離契約。
- `reporting-and-sharing`: HTML／CSV 報告、MotherDuck 單向分享與失敗時的安全退化行為。

### Modified Capabilities

(none)

## Impact

- 新增 Python 3.12 套件、命令列工具、測試、範例設定與原生 Windows PowerShell 腳本。
- 新增 DuckDB／MotherDuck、HTTPX、Typer、Jinja2 等相依套件。
- 新增本機 `data/` 儲存邊界；資料庫、備份、API 金鑰、真實料號清單與報告不得進入 Git。
- 建立 Future Electronics API 與 MotherDuck 的外部整合點，但所有預設測試保持離線。
- Mouser API、網頁後端、自動下單與股票交易不在第一版範圍內。
