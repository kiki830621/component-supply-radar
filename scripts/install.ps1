param(
    [switch]$WhatIf,
    [switch]$SkipUvInstall,
    [switch]$SkipSelfCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "common.ps1")

function Write-Step {
    param([string]$Message)
    Write-Host "[Component Supply Radar] $Message"
}

function Invoke-Uv {
    param(
        [string[]]$Arguments,
        [string]$DisplayName
    )
    Invoke-CheckedCommand -Command $script:UvCommand -Arguments $Arguments -DisplayName $DisplayName
}

$IsNativeWindows = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
if (-not $IsNativeWindows) {
    throw "install.ps1 僅支援原生 Windows 10 或 Windows 11。"
}

$RepositoryRoot = Get-RepositoryRoot
$RequiredFiles = @(
    "pyproject.toml",
    "uv.lock",
    ".env.example",
    "examples\supplier-observations.csv"
)
foreach ($RelativePath in $RequiredFiles) {
    $RequiredPath = Join-Path $RepositoryRoot $RelativePath
    if (-not (Test-Path -LiteralPath $RequiredPath -PathType Leaf)) {
        throw "專案檔案不完整：找不到 $RelativePath"
    }
}

if ($WhatIf) {
    Write-Step "預覽：確認或安裝 uv，準備 Python 3.12，執行 uv sync --frozen --no-dev。"
    Write-Step "預覽：保留既有 .env 與 data，建立缺少的資料夾並初始化 DuckDB。"
    if (-not $SkipSelfCheck) {
        Write-Step "預覽：執行 work\install-check.duckdb 離線自我檢查。"
    }
    exit 0
}

$script:UvCommand = Get-UvCommand
if ($null -eq $script:UvCommand) {
    if ($SkipUvInstall) {
        throw "找不到 uv。請先執行：winget install --id astral-sh.uv -e"
    }
    $Winget = Get-Command -Name winget -ErrorAction SilentlyContinue
    if ($null -eq $Winget) {
        throw "找不到 uv 或 winget。請依 Astral 官方文件安裝 uv：https://docs.astral.sh/uv/getting-started/installation/"
    }
    Write-Step "正在透過 winget 安裝 uv。"
    Invoke-CheckedCommand -Command $Winget.Source -Arguments @(
        "install",
        "--id", "astral-sh.uv",
        "-e",
        "--accept-package-agreements",
        "--accept-source-agreements"
    ) -DisplayName "uv 安裝"
    Update-ProcessPath
    $script:UvCommand = Get-UvCommand
}
if ($null -eq $script:UvCommand) {
    throw "uv 安裝後仍無法找到。請關閉 PowerShell、重新開啟，再重跑 install.ps1。"
}

Push-Location $RepositoryRoot
try {
    Write-Step "正在準備 Python 3.12。"
    Invoke-Uv -Arguments @("python", "install", "3.12") -DisplayName "Python 3.12 安裝"

    Write-Step "正在依 uv.lock 安裝正式環境相依套件。"
    $SyncArguments = @("sync", "--frozen", "--no-dev")
    Invoke-Uv -Arguments $SyncArguments -DisplayName "相依套件安裝"

    $EnvironmentFile = Join-Path $RepositoryRoot ".env"
    if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
        Copy-Item -LiteralPath (Join-Path $RepositoryRoot ".env.example") -Destination $EnvironmentFile
        Write-Step "已建立 .env；請稍後填入 Future API key。"
    }
    else {
        Write-Step "保留既有 .env。"
    }

    foreach ($RelativeDirectory in @("data", "data\backups", "data\logs", "reports", "work")) {
        $Directory = Join-Path $RepositoryRoot $RelativeDirectory
        if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
            New-Item -ItemType Directory -Path $Directory | Out-Null
        }
    }

    $WatchlistFile = Join-Path $RepositoryRoot "data\watchlist.csv"
    if (-not (Test-Path -LiteralPath $WatchlistFile)) {
        Copy-Item -LiteralPath (Join-Path $RepositoryRoot "config\watchlist.example.csv") `
            -Destination $WatchlistFile
        Write-Step "已建立 data\watchlist.csv；正式收集前請換成要追蹤的料號。"
    }
    else {
        Write-Step "保留既有 data\watchlist.csv。"
    }

    $DatabasePath = Join-Path $RepositoryRoot "data\radar.duckdb"
    Invoke-Uv -Arguments @(
        "run", "component-supply-radar", "--database", $DatabasePath, "init-db"
    ) -DisplayName "DuckDB 初始化"

    if (-not $SkipSelfCheck) {
        $CheckDatabase = Join-Path $RepositoryRoot "work\install-check.duckdb"
        $CheckReport = Join-Path $RepositoryRoot "work\install-check-report"
        $ExampleCsv = Join-Path $RepositoryRoot "examples\supplier-observations.csv"
        Invoke-Uv -Arguments @(
            "run", "component-supply-radar", "--database", $CheckDatabase, "init-db"
        ) -DisplayName "離線資料庫初始化"
        Invoke-Uv -Arguments @(
            "run", "component-supply-radar", "--database", $CheckDatabase,
            "import-csv", $ExampleCsv
        ) -DisplayName "離線範例匯入"
        Invoke-Uv -Arguments @(
            "run", "component-supply-radar", "--database", $CheckDatabase, "analyze"
        ) -DisplayName "離線分析"
        Invoke-Uv -Arguments @(
            "run", "component-supply-radar", "--database", $CheckDatabase,
            "report", "--output", $CheckReport
        ) -DisplayName "離線報告產生"
    }
}
finally {
    Pop-Location
}

Write-Step "安裝完成。下一步請編輯 .env 與 data\watchlist.csv。"
