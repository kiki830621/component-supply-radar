## 1. 專案骨架與政策契約

- [x] 1.1 建立 Python 3.12 `src/` 套件、`uv` 相依套件、Ruff／mypy／pytest 設定、`.gitignore` 與 `.env.example`，使全新環境可執行 `uv sync`、`uv run component-supply-radar --help`，並以 `test_package_bootstrap` 驗證預設不需要正式金鑰。
- [x] 1.2 實作 `Source rights are machine-readable` 與 `Secrets and generated data remain outside Git`：來源政策完整包含六個權利欄位，禁止保存時在任何 persistent sink 前失敗；以 `test_forbidden_source_never_reaches_sink` 與秘密掃描驗證。
- [x] [P] 1.3 定義標準 Observation、PriceBreak、panel member、分類、曝險與 run result 型別，使 `Interface and data shape` 中所有欄位有固定型別與 UTC／Decimal 約束；以模型邊界測試與 `uv run mypy src` 驗證。

## 2. 料號池、分類與離線輸入

- [x] 2.1 實作 `Collection is limited to a versioned watch panel`、`Dual raw and canonical taxonomy`、`Versioned core and exploratory watch panels` 及 `Raw and canonical categories are both retained`：只查 active panel 成員、core 才進正式指數、兩種分類皆可稽核；以 `test_exploratory_member_is_excluded_from_official_panel` 和 mapping fixture 驗證。
- [x] [P] 2.2 實作 `User-owned CSV ingestion is offline and auditable`：合法 CSV 能離線正規化、以檔案雜湊避免重複，錯誤數量／時間／幣別被拒絕；以 `tests/test_csv_import.py` 的有效、重複與無效案例驗證。

## 3. Future 收集與執行稽核

- [x] 3.1 實作 `Future Electronics is the sole automated distributor source`、`Future-only automated source and policy metadata` 及 `Future requests use bounded batches and explicit failures`：Future client 每批最多 300 MPN、正規化區域庫存／在途／交期／價格，終止與暫時錯誤可區分，且沒有 Mouser 或網頁收集程式；以 HTTPX fixture、request-count assertion 和 `rg` 範圍檢查驗證。
- [x] 3.2 實作 `Collection runs are distinguishable from zero inventory` 與 `Failure modes`：最多三次暫時錯誤嘗試、授權錯誤不重試、失敗不寫成零庫存、run 記錄 success／partial／failed；以 `tests/test_pipeline.py` 驗證所有狀態與去敏錯誤。

## 4. DuckDB 歷史儲存與備份

- [x] 4.1 實作 `Local DuckDB is the writable authority` 與 `Observation writes are transactional and idempotent`：有版本 schema、固定精度價格、deterministic hash、同批交易與重跑不重複；以暫存 DuckDB 整合測試和 `test_transaction_rolls_back_invalid_batch` 驗證。
- [x] [P] 4.2 實作 `Weekly Parquet backups are bounded and self-describing`：完整備份帶 schema version／export time 並只保留最近 12 份；以建立第 13 份備份的 retention 測試及 DuckDB 讀回 Parquet 驗證。

## 5. 壓力指數與警訊狀態

- [x] 5.1 實作 `Part pressure uses transparent bounded components`、`Official category pressure uses core-panel robust aggregation`、`Category output includes coverage` 與 `Robust category intensity and breadth aggregation`：0–100 料號分數、核心中位數、惡化廣度與覆蓋欄位符合規範；以公式邊界表、極端值中位數和 exploratory 排除測試驗證。
- [x] 5.2 實作 `Alerts use a multi-stage state machine` 與 `Multi-stage alert state machine`：normal／watch／confirmed／recovering／unknown 的七日狀態轉換可重現，失敗或覆蓋不足不會被當成恢復；以狀態轉換參數化測試驗證。

## 6. 公司曝險研究模型

- [x] [P] 6.1 實作 `Direct manufacturer exposure is evidence-backed`、`Thematic exposure is separate and labeled as a research assumption`、`Exposure output does not provide trade instructions` 及 `Split direct and thematic company exposure`：兩類 mapping 分離、帶版本／審閱／證據，且不改變壓力分數；以 provenance、score invariance 與禁止交易措辭測試驗證。

## 7. 報告、MotherDuck 與操作介面

- [x] 7.1 實作 `Reports expose pressure, breadth, coverage, and provenance`：HTML 與 UTF-8 CSV 呈現 Asia/Taipei 時間、來源、強度、廣度、覆蓋、狀態及兩層曝險，資料不足不轉成零；以 Jinja escaping、CSV 欄位與 snapshot assertion 驗證。
- [x] 7.2 實作 `MotherDuck publication is one-way and policy-gated`、`Cloud publication failure does not corrupt local authority` 及 `DuckDB authority and MotherDuck read-only sharing`：只同步允許分享來源、無 token 略過、同步失敗不改本機；以暫存 DuckDB 目標和注入失敗測試驗證。
- [x] 7.3 實作 `Observable behavior`：CLI 提供 `init-db`、`import-csv`、`collect-future`、`analyze`、`report`、`sync`、`backup`、`run-daily`，每階段狀態可辨識；以 Typer runner 與範例 CSV 端到端測試驗證。
- [x] [P] 7.4 實作 `Native Windows installation and scheduling` 與 `Native Windows scheduling is repeatable`：提供原生 Windows PowerShell 安裝器，以及目前使用者工作排程的安裝、查詢與移除；相依套件依 `uv.lock` frozen 安裝，既有設定與資料不得覆寫，日誌位於 ignored `data/logs/`；以腳本契約、PowerShell parser、dry-run 與 `windows-latest` 離線流程驗證。

## 8. 文件與完整驗收

- [x] 8.1 撰寫 Windows-first README，使操作者能完成原生 Windows 安裝、Future API 申請、來源權利設定、watch panel、CSV 匯入、MotherDuck 分享、工作排程、備份、更新、解除安裝、容量估算與疑難排解；以全新 `windows-latest` 環境逐條執行離線 quickstart 驗證。
- [x] 8.2 核對 `Acceptance criteria` 與 `Scope boundaries`：預設離線測試、冪等、exploratory 排除、公式／狀態邊界、無 token 本機流程、無 Mouser／Supabase／網頁／交易功能；以需求追蹤表、`spectra analyze build-future-supply-radar --json` 與 `spectra validate build-future-supply-radar` 驗證。
- [x] 8.3 執行完整品質閘門 `uv run pytest -q`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy src`、CLI help、示範端到端流程、`git diff --check` 與秘密掃描，所有命令退出碼為零且未追蹤任何生成資料後才宣告完成。
