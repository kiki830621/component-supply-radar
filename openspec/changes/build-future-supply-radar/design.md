## Context

Spectra discuss 已把第一版收斂為 Future Electronics 單一自動 API、自有 CSV 備援、本機 DuckDB 權威資料庫、MotherDuck 唯讀分享及 Parquet 備份。系統服務兩至三位內部研究使用者，正式交付環境是原生 Windows 10／11；API 金鑰與實際料號資料不得進入 Git。

最大的分析風險是把單一通路庫存變化誤稱為整體市場供應變化，或把料號壓力直接誤解成股票交易訊號。因此系統必須保留來源、樣本覆蓋、分類版本與公司關係的證據層級。

## Goals / Non-Goals

**Goals:**

- 每日、可重跑且可稽核地收集指定 Future MPN。
- 保存獲准欄位的歷史快照、價格級距與執行狀態。
- 產生不受大型料號或單日異常主導的分類壓力指標。
- 以明確狀態區分早期觀察、持續壓力、恢復與資料未知。
- 讓內部使用者可透過 MotherDuck 查詢獲准分享的標準化資料。
- 在沒有正式 API 或 MotherDuck token 時仍能以範例 CSV 完成離線流程。

**Non-Goals:**

- 不實作 Mouser、網頁爬取、Cloudflare 繞過、完整目錄下載或自動下單。
- 不建立網頁後端、即時串流、手機 App 或公開儀表板。
- 不產生股票買賣、部位大小或報酬預測。
- 不將 Future 通路壓力宣稱為整體半導體市場供需。

## Decisions

### Future-only automated source and policy metadata

第一版只整合 Future Product Info API，因為它直接提供跨區域可售庫存、工廠庫存、在途量、交期和價格級距，且能以最多 300 個 MPN 批次查詢。自有 CSV 使用相同標準化資料型別，讓離線測試與手動補充不依賴正式金鑰。

每個來源都必須具備可執行的權利政策；API 申請或合約若有更嚴限制，以其為準。替代方案是同時整合 Mouser，但其保存限制會使歷史分析與 MotherDuck 分享不可行，因此第一版排除。

### Dual raw and canonical taxonomy

同時保存供應商原始分類及有版本的內部標準分類。原始值提供稽核，標準分類提供跨日穩定分析。只保存其中一種會分別犧牲可比性或來源脈絡。

### Versioned core and exploratory watch panels

`core` 料號負責正式指數，只能在有版本、有生效日期的換樣流程中調整；`exploratory` 可隨時加入研究，但不回寫正式歷史指數。這比完全固定更能處理停產，也比動態熱門清單更能維持時間可比性。

### DuckDB authority and MotherDuck read-only sharing

本機 DuckDB 是唯一可寫入的權威資料庫。每日流程先完成本機交易、訊號與報告，再把政策允許的標準化表單向發布到 MotherDuck。MotherDuck 不反向修改本機資料；沒有 token 時只略過同步。

替代方案是讓 MotherDuck 成為唯一資料庫，但網路失敗會阻塞桌機收集，也會使授權與復原界線更難稽核。

### Native Windows installation and scheduling

一般使用者透過 PowerShell 安裝器與 `uv.lock` 準備 Python 3.12 及固定版本相依套件，不需要預先安裝 Python。每日流程由目前登入使用者的 Windows 工作排程呼叫固定 `run_daily.ps1`；安裝、查詢與移除排程都不得保存 Windows 密碼或刪除本機資料。

替代方案是把程式封裝成單一執行檔，但 API 設定、資料庫、排程與更新仍需外部管理，且會降低相依套件透明度，因此不採用。

### Robust category intensity and breadth aggregation

先在各 MPN 自己的歷史尺度上計算 0–100 壓力，再以核心料號分數中位數表示分類強度、以超過門檻的比例表示廣度。每次輸出都帶有效核心數、設定核心數、來源數與資料充分性。

不依絕對庫存或價格加權，因為單一通路的庫存規模不能當成市場規模；不使用算術平均，避免少數極端料號主導。

### Multi-stage alert state machine

狀態為 `normal`、`watch`、`confirmed`、`recovering`、`unknown`。單次強度至少 60 先進入 `watch`；七天內至少三次強度達 60 且最新強度至少 70 才進入 `confirmed`。曾 confirmed／recovering 的分類降到 40–59 時為 `recovering`，低於 40 才回到 `normal`。收集失敗或覆蓋不足一律是 `unknown`，不能當成恢復。

### Split direct and thematic company exposure

直接曝險只由 MPN 製造商與經人工審閱的 issuer mapping 建立；上下游、替代供應商與受益／受害假說放在獨立 thematic mapping，明確標示為人工研究假設。兩者都不改變客觀供應壓力分數。

## Implementation Contract

### Observable behavior

安裝後提供 `component-supply-radar` CLI，至少包含 `init-db`、`import-csv`、`collect-future`、`analyze`、`report`、`sync`、`backup` 與 `run-daily`。使用範例 CSV 時，全新環境不需任何金鑰即可建立資料庫、匯入、分析並產生 HTML／CSV。

`run-daily` 依序執行本機初始化、Future 收集（有金鑰時）、訊號更新、報告、MotherDuck 同步（有 token 且政策允許時）及到期備份工作。每個階段的成功、略過、部分成功或失敗都必須在終端與執行紀錄中可辨識。

原生 Windows 安裝入口為 `scripts\install.ps1`。安裝器必須可重複執行、依 `uv.lock` frozen 安裝、不覆寫 `.env` 或 `data\watchlist.csv`，並以離線範例驗證 DuckDB、分析及報告流程。Windows 工作名稱固定為 `ComponentSupplyRadar-Daily`。

### Interface and data shape

標準 observation 包含來源、MPN、製造商、UTC 觀測時間、原始與標準分類、taxonomy version、panel version／role、區域庫存、工廠庫存、在途量、最低量、訂購倍數、交期天數、生命週期、幣別、價格級距、選用的來源檔案 hash 與 deterministic ingestion hash。

來源政策包含 `persist_allowed`、`cloud_share_allowed`、`raw_retention_days`、`attribution_required`、`terms_reviewed_at` 與 `terms_url`。報告列包含分類強度、廣度、有效／設定核心數、來源數、資料狀態、警訊狀態、直接曝險與主題曝險 provenance。

### Failure modes

- Future 401／402／403／406：停止該來源，不重試，記錄去敏錯誤。
- Future 429／5xx：最多三次總嘗試，仍失敗則標記 partial 或 failed。
- 個別回應驗證失敗：不寫入錯誤 observation，且不得轉成零庫存。
- MotherDuck 失敗：本機資料與報告保持完成，同步階段回報失敗。
- 覆蓋不足或收集失敗：分類狀態為 `unknown`。

### Acceptance criteria

- 預設離線測試不呼叫正式 API，且能驗證 Future fixture 正規化。
- 同一 CSV 或 API observation 重跑不產生重複資料。
- exploratory 料號不改變正式分類指數。
- 壓力公式與狀態轉換具邊界測試。
- 無 MotherDuck token 時，本機端到端流程仍成功。
- 測試、格式、靜態檢查、型別檢查、CLI help、示範端到端流程、秘密掃描與 `spectra validate` 全部通過。
- Windows CI 能在乾淨的 `windows-latest` runner 完成 frozen 安裝、PowerShell 剖析與離線 quickstart。

### Scope boundaries

實作只包含 proposal 所列五項 capability。任何網頁、Supabase、Mouser、其他 distributor、交易策略或公開發布都需要新的 Spectra change。

## Risks / Trade-offs

- [單一通路偏誤] → 報告一律稱為 Future 通路壓力，附來源與覆蓋，不宣稱整體市場代表性。
- [Future API 合約限制保存或分享] → 以機器可執行政策阻擋 persistence／cloud sink，並以自有 CSV 維持離線流程。
- [料號池換樣造成歷史斷裂] → 核心 panel 有版本與生效日期，探索 panel 不回寫正式指數。
- [公司關係過度推論] → 直接與主題曝險分表、保留證據並禁止交易指令。
- [MotherDuck 暫時不可用] → 本機 DuckDB 先提交且可獨立報告，雲端只是一方向分享副本。
