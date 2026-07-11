# Component Supply Radar 設計規格

日期：2026-07-11

## 1. 目標

建立一套可在 macOS 桌機每日執行的電子零件供應觀測系統，針對精選製造商料號（MPN）累積合規的庫存、價格級距與交期歷史，計算供應緊張訊號，並產生可分享的 HTML 與 CSV 報告。

本系統是研究輔助工具，不構成投資建議，也不宣稱供應鏈訊號能單獨預測股價。第一版以可重現、可稽核、低成本和資料授權合規為優先。

## 2. 第一版範圍

### 包含

- 追蹤 300 至 1,000 個指定 MPN，而非下載供應商完整商品目錄。
- 支援 Future Electronics API、使用者提供的 CSV，以及 Mouser 即時查詢。
- 儲存獲准保存來源的每日標準化快照。
- 使用 DuckDB 進行本機分析。
- 將獲准分享的標準化資料單向同步至 MotherDuck，供最多三位內部使用者查詢。
- 每週輸出 Parquet 備份。
- 計算庫存下降、價格上漲、交期拉長、缺貨廣度與綜合供應緊張分數。
- 產生 HTML 摘要報告與 CSV 明細。
- 提供 macOS `launchd` 每日排程安裝與移除指令。
- 提供完整 README、環境變數範例、觀察清單範例和離線測試。

### 不包含

- 自動下單或交易股票。
- 繞過 Cloudflare、CAPTCHA、登入或其他網站防護。
- 把 API 金鑰、MotherDuck token、原始資料庫或供應商資料提交到 Git。
- 未經供應商允許的完整目錄下載、批次爬取或歷史保存。
- 第一版的網頁儀表板、手機 App、即時串流或機器學習價格預測。

## 3. 資料來源與合規界線

### Future Electronics

使用官方 REST API，以授權金鑰查詢指定 MPN。介面可取得庫存、工廠庫存、在途量、最低訂購量、工廠交期、區域庫存和價格級距。只有在使用者的實際授權條款允許保存與分析時，才開啟歷史寫入和 MotherDuck 同步。

官方參考：<https://media.futureelectronics.com/doc/Future-Electronics-API-Guide.pdf>

### Mouser

官方 Search API 可提供價格、庫存和交期，但現行公開條款禁止快取、記錄或以 API 內容建立自有資料庫。因此第一版的 Mouser adapter 僅支援即時查詢和終端顯示，不把回傳內容寫入 DuckDB、日誌、報告或測試快照。只有在取得 Mouser 書面授權並更新來源政策設定後，才能開啟保存功能。

官方參考：<https://www.mouser.com/apihome/>、<https://www.mouser.com/en/apiterms/>

### 使用者 CSV

使用者擁有或已獲授權的供應商匯出檔是第一版可完整保存的基準來源。匯入器會驗證欄位、幣別、時間、數量與 MPN，並保留來源檔雜湊以避免重複匯入。

### 公開市場報告

README 會列出 Future Electronics Market Conditions Report、ECIA、SIA、WSTS、SEMI 與 TTI MarketEye 等參考來源。第一版只保存報告網址、發布日期和使用者筆記，不自動重製或大量擷取受著作權保護的報告內容。

## 4. 儲存架構

### 本機主要資料庫

`data/radar.duckdb` 是唯一可寫入的主要資料庫。每日收集程序在單一交易中寫入快照、價格級距、執行紀錄與訊號。資料庫和 `data/` 全部由 `.gitignore` 排除。

### MotherDuck 分享層

同步程序將授權允許分享的標準化資料單向發布到 MotherDuck。桌機資料庫是權威來源；MotherDuck 第一版為唯讀分享層，不接受反向寫入，以避免同步衝突。未設定 `MOTHERDUCK_TOKEN` 時，所有本機功能仍可正常運作。

### Parquet 備份

每週依資料表和年月輸出壓縮 Parquet 到 `data/backups/YYYY-MM-DD/`。備份包含資料結構版本與匯出時間。第一版保留最近 12 份本機週備份；Cloudflare R2 只保留為後續選配，不是執行必要條件。

### 原始回應保留

- 只有來源條款明確允許時才保存原始回應。
- 獲准保存的原始回應最多保留 30 天，之後由清理工作刪除。
- Mouser 原始回應保留時間固定為零。
- 長期分析只依賴標準化欄位和來源稽核資訊。

## 5. 資料模型

### `parts`

- `mpn`：正規化製造商料號，主鍵的一部分。
- `manufacturer`：製造商名稱。
- `category`：自訂觀察分類。
- `ticker`：可選的上市公司代號，僅作分組研究。
- `active`：是否納入每日觀察。
- `notes`：使用者備註。

### `sources`

- `source_id`：穩定來源代號。
- `display_name`：顯示名稱。
- `storage_policy`：`forbidden`、`licensed` 或 `user_owned`。
- `raw_retention_days`：允許的原始資料保留天數。
- `cloud_share_allowed`：是否允許同步至 MotherDuck。

### `collection_runs`

- `run_id`：UUID。
- `source_id`、開始與完成時間、成功／部分成功／失敗狀態。
- 請求數、成功料號數、失敗料號數和去敏後錯誤摘要。
- 不保存 API 金鑰、授權 header 或禁止保存的回應內容。

### `observations`

- `source_id`、`mpn`、`observed_at_utc` 組成自然唯一鍵。
- 可售庫存、工廠庫存、在途量、最低訂購量、訂購倍數。
- 標準化交期天數及原始交期單位。
- 幣別、生命週期、區域與資料品質旗標。
- `ingest_hash` 用於冪等寫入。

### `price_breaks`

- 關聯到 observation。
- 起始數量、結束數量、單價與幣別。
- 單價使用 `DECIMAL(18, 6)`，避免浮點誤差。

### `signals`

- 每日每料號的 7 日與 30 日庫存變化率。
- 最低可比較價格的 7 日與 30 日變化率。
- 交期變化天數。
- 缺貨旗標與跨來源缺貨比例。
- 0 至 100 的綜合緊張分數，以及觸發原因陣列。

## 6. 訊號定義

第一版採透明規則，不使用不可解釋模型：

- 庫存分數 0–35：30 日庫存跌幅達 50% 時取得滿分；增加時為零。
- 交期分數 0–25：30 日交期增加 56 天時取得滿分。
- 價格分數 0–25：30 日可比較數量級距價格上漲 20% 時取得滿分。
- 缺貨廣度 0–15：獲准保存的來源全部缺貨時取得滿分。
- 綜合分數限制在 0–100。
- 少於兩筆可比較歷史資料時，分數標示為資料不足，不以零取代。

報告以料號、分類、製造商與 ticker 分組，清楚顯示觀測值、比較基準、資料來源與資料不足狀態。任何 ticker 聚合都只是供應鏈觀察，不產生買賣建議。

## 7. 程式元件

- `config`：載入環境變數、追蹤清單和來源政策。
- `providers`：每個供應商一個 adapter，輸出共同的標準化資料型別。
- `storage`：DuckDB schema、交易寫入、查詢和遷移。
- `pipeline`：安排批次、速率限制、重試、冪等和執行稽核。
- `signals`：以 SQL／Python 計算透明指標。
- `reports`：輸出 HTML 與 CSV。
- `sync`：單向發布允許分享的資料至 MotherDuck。
- `backup`：Parquet 匯出和 12 週保留政策。
- `cli`：`init-db`、`collect`、`import-csv`、`analyze`、`report`、`sync`、`backup`、`run-daily` 和 `mouser-live`。

## 8. 每日資料流程

1. 讀取觀察清單與來源政策。
2. 建立 collection run，逐來源批次查詢。
3. 對 429 和 5xx 採指數退避；401、402、403 立即停止該來源且不重試。
4. 驗證並正規化回應；禁止保存的來源只回傳至終端。
5. 在 DuckDB 交易中冪等寫入允許保存的資料。
6. 計算訊號並產生報告。
7. 若有 MotherDuck token，單向同步允許分享的資料。
8. 每週執行 Parquet 備份與保留清理。

資料庫時間一律使用 UTC；README、CLI 與 HTML 報告顯示 Asia/Taipei 時間。

## 9. 錯誤處理與安全

- API 金鑰只由環境變數或本機 `.env` 讀取，`.env` 永不進 Git。
- 日誌會遮蔽 token、授權 header 和可能含憑證的網址參數。
- 單一料號失敗不會使整批資料回滾；來源授權失敗會停止該來源。
- 所有網路請求都有連線與讀取逾時、有限次重試和可辨識的 User-Agent。
- 收集結果可為 `success`、`partial` 或 `failed`，報告不得把失敗誤呈現為零庫存。
- schema 變更透過有版本的遷移執行，不直接手動修改正式資料庫。

## 10. 測試與驗收

- 單元測試涵蓋設定、各 provider 正規化、資料政策、訊號邊界、備份保留與去敏。
- 整合測試使用本機暫存 DuckDB 和固定 JSON／CSV fixture，不呼叫正式 API。
- Future 與 MotherDuck 的 live smoke test 必須由使用者明確啟用，預設測試不需要任何金鑰。
- Mouser 測試驗證禁止寫入政策，包括禁止寫入資料庫、檔案、日誌與報告。
- 相同批次重跑兩次不得產生重複 observation 或 price break。
- README 從全新 Python 環境開始的安裝、初始化、範例匯入、報告與排程指令必須可照做。
- 完整驗收包含測試、靜態檢查、型別檢查、CLI help、示範資料端到端執行與秘密掃描。

## 11. GitHub 邊界

建立 `kiki830621/component-supply-radar` private repo，預設分支為 `main`。Git 只保存程式、測試、文件、fixture 和不含真實商業資料的示範檔。

下列內容必須忽略：

- `.env` 和所有金鑰。
- `data/`、DuckDB、Parquet 備份與實際報告。
- 使用者真實觀察清單（另提供不含敏感資料的範例）。
- API 原始回應與執行日誌。

## 12. 成功條件

第一版完成時，使用者可在新環境依 README：

1. 安裝 Python 相依套件。
2. 建立本機 DuckDB。
3. 匯入示範或自有 CSV。
4. 產生具有供應緊張分數的 HTML／CSV 報告。
5. 選擇性設定 Future 與 MotherDuck 金鑰。
6. 安裝每日 `launchd` 排程。
7. 執行每週 Parquet 備份。
8. 確認任何禁止保存的 Mouser 資料都未落地。
