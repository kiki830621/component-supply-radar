# Component Supply Radar Windows 交付設計

日期：2026-07-12

## 1. 目標與使用者

將 Component Supply Radar 交付為可由一般 Windows 10／11 使用者安裝、設定與每日執行的私人研究工具。使用者不需要預先安裝 Python，也不需要自行建立虛擬環境或逐一管理套件版本。

正式支援原生 Windows PowerShell；macOS `launchd` 腳本不再出現在主要安裝流程。程式仍維持 Python 專案形式，不封裝成單一執行檔，以保留透明度、可測試性及日後更新能力。

## 2. 建議交付方式

採用「PowerShell 安裝器 + uv 鎖定環境」：

- `uv.lock` 是正式相依套件鎖定來源。
- `scripts/install.ps1` 處理工具檢查、Python 3.12、相依套件、資料目錄、環境設定檔與離線自我檢查。
- 所有日常指令仍透過 `uv run component-supply-radar ...` 執行，避免依賴使用者目前啟用的 Python 環境。
- 若電腦沒有 `uv`，安裝器優先使用 Windows Package Manager；無法使用時顯示 Astral 官方安裝指令與可操作的錯誤說明。
- 使用者可從私人 GitHub repository 複製專案，或下載 repository ZIP 後解壓縮。GitHub 存取權的設定不由安裝器代辦。

不採用手動 `pip`，因為容易混用系統 Python 且無法完整重現鎖定環境。不採用單一 `.exe`，因為 API 設定、資料檔、排程與版本更新仍需外部管理，反而增加維護成本。

## 3. Windows 安裝流程

README 的一般使用者流程固定為：

1. 取得私人 repository 或 ZIP，放在不會任意移動的位置。
2. 以一般使用者身分開啟 PowerShell，不要求系統管理員權限。
3. 在專案根目錄執行 `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1`。
4. 安裝器確認作業系統與專案檔案，準備 `uv` 和 Python 3.12，並執行 `uv sync --frozen`。
5. 若 `.env` 不存在，從 `.env.example` 建立；既有 `.env` 永不覆寫。
6. 建立 `data\`、`data\backups\`、`data\logs\` 與 `reports\`，初始化 `data\radar.duckdb`。
7. 使用不含正式商業資料的範例 CSV 執行離線匯入、分析與 HTML／CSV 報告，確認完整資料路徑可用。
8. 顯示下一步：編輯 `.env`、複製自己的 watchlist、執行第一次 Future 收集，以及選擇是否安裝每日排程。

安裝器必須可重複執行。重跑不得刪除 `.env`、DuckDB、報告、備份、真實 watchlist 或日誌。

## 4. 使用者操作腳本

新增以下 Windows PowerShell 腳本：

- `scripts/install.ps1`：安裝及離線自我檢查。
- `scripts/run_daily.ps1`：切換到固定專案目錄，執行每日收集、分析、報告、同步及到期備份，並將輸出追加到 `data\logs\`。
- `scripts/install_scheduled_task.ps1`：以目前使用者建立每天 07:30 執行的 Windows 工作排程，不保存使用者密碼。
- `scripts/scheduled_task_status.ps1`：顯示工作是否存在、目前狀態、上次結果與下次執行時間。
- `scripts/uninstall_scheduled_task.ps1`：只移除本專案工作排程，不刪除程式或資料。
- `scripts/open_latest_report.ps1`：開啟最新 HTML 報告；沒有報告時提供先執行哪個指令的說明。

腳本必須以自身位置推導 repository 根目錄，避免依賴使用者從特定目錄執行。含空白的 Windows 路徑必須正確引用。

## 5. 工作排程契約

Windows 工作名稱固定為 `ComponentSupplyRadar-Daily`，預設每天 07:30 執行。排程呼叫 `run_daily.ps1`，而不是把長串 Python 參數直接寫進工作定義。

安裝排程前先確認安裝流程已完成。重複安裝會更新既有工作；移除不存在的工作視為成功。所有腳本提供 `-WhatIf` 或等效預覽模式，讓使用者先看預計動作。

正式資料仍在 repository 的 `data\` 下。排程失敗不得把失敗的 API 查詢寫成零庫存；錯誤寫入 `data\logs\daily-error.log`，本機 DuckDB 保持權威來源。

## 6. README 與相關文件

README 改為 Windows 優先，依下列順序編排：

1. 工具用途、限制與資料授權界線。
2. 一般使用者快速安裝。
3. 安裝完成驗證與資料實際存放位置。
4. Future API key 申請與 `.env` 設定。
5. watchlist 欄位、複製範例與真實資料保密方式。
6. 第一次手動收集、分析、產生及開啟報告。
7. Windows 每日工作排程的安裝、查詢與移除。
8. MotherDuck 選擇性分享。
9. Parquet 備份、容量估算與復原觀念。
10. 更新、重新安裝與解除安裝。
11. 常見錯誤及對應處理。
12. 開發者測試與 Windows CI。

所有命令採 PowerShell 可直接貼上的語法。macOS 指令若保留，只能放在獨立的非正式相容性附錄，不能混入主要流程。

專案中仍描述 macOS 為唯一支援平台、把 `launchd` 當主要排程，或宣稱含有未實作 Mouser 自動來源的說明都必須同步修正。歷史設計文件若保留，必須清楚標示已被目前 Future-only Windows 契約取代。

## 7. 相依套件與版本政策

- Python 最低版本維持 3.12，安裝器要求 `uv` 使用 3.12 系列。
- 一般使用者執行 `uv sync --frozen`，只能安裝 `uv.lock` 中已解析的版本；鎖定檔與 `pyproject.toml` 不一致時直接失敗。
- 開發者使用 `uv sync --all-groups --frozen` 安裝測試、Ruff 與 mypy。
- API 金鑰及 token 只放在 ignored `.env`，不得出現在 PowerShell 命令列、工作排程參數或 Git。
- 更新流程為先備份 `data\`，再取得新版程式並重跑 `install.ps1`；安裝器保留既有資料與設定。

## 8. 錯誤處理

PowerShell 腳本使用嚴格錯誤模式，任何外部命令非零退出都停止並顯示失敗階段。錯誤訊息至少區分：

- 非 Windows 環境。
- repository 不完整或工作目錄錯誤。
- `uv` 安裝後仍無法找到。
- Python 或相依套件下載失敗。
- `.env` 缺少 Future API key。
- Future 授權錯誤、暫時性錯誤與部分成功。
- 工作排程建立、查詢或移除失敗。
- DuckDB 被其他程序鎖定。

安裝失敗不得刪除既有資料。離線自我檢查使用 `work\install-check.duckdb` 與 `work\install-check-report\`，避免污染正式資料；成功後可清除這些暫存項目。

## 9. 驗證策略

Windows 交付需要三層驗證：

1. Python 測試：維持所有現有 pytest、Ruff 與 mypy 品質閘門。
2. PowerShell 契約測試：驗證腳本可剖析、使用嚴格錯誤模式、由腳本位置解析根目錄、正確引用含空白路徑、不覆寫 `.env`，以及排程安裝／移除的預覽輸出。
3. GitHub Actions Windows job：在乾淨的 `windows-latest` runner 安裝 `uv`，執行 frozen sync、完整測試、CLI help 與 README 離線 quickstart。

正式 Future API 與 MotherDuck 不在 CI 呼叫；網路 provider 使用固定 fixture。CI 不需要任何秘密。

## 10. 完成條件

- 一般 Windows 10／11 使用者從乾淨環境能依 README 安裝，不需預先安裝 Python。
- `install.ps1` 能在含空白路徑中成功重跑，且不改動既有設定與資料。
- 離線 quickstart 能初始化、匯入範例、分析並產生可開啟的 HTML／CSV 報告。
- 工作排程可安裝、查詢、手動測試及移除。
- README 明確說明 DuckDB、Parquet、日誌、報告、`.env` 與 MotherDuck 的位置及角色。
- Windows CI、pytest、Ruff、格式檢查、mypy、CLI help、秘密掃描與文件一致性檢查全部通過。
