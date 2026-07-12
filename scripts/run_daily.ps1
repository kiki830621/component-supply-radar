Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "common.ps1")

$RepositoryRoot = Get-RepositoryRoot
$UvCommand = Get-UvCommand
if ($null -eq $UvCommand) {
    throw "找不到 uv。請先執行 scripts\install.ps1。"
}

$LogDirectory = Join-Path $RepositoryRoot "data\logs"
if (-not (Test-Path -LiteralPath $LogDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $LogDirectory | Out-Null
}
$OutputLog = Join-Path $LogDirectory "daily-output.log"
$ErrorLog = Join-Path $LogDirectory "daily-error.log"
$WatchlistFile = Join-Path $RepositoryRoot "data\watchlist.csv"
if (-not (Test-Path -LiteralPath $WatchlistFile -PathType Leaf)) {
    throw "找不到 data\watchlist.csv。請先執行 scripts\install.ps1。"
}
$StartedAt = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
Add-Content -LiteralPath $OutputLog -Value "[$StartedAt] 每日流程開始"

Push-Location $RepositoryRoot
try {
    $Arguments = @(
        "run", "component-supply-radar", "run-daily",
        "--watchlist", $WatchlistFile,
        "--output", (Join-Path $RepositoryRoot "reports"),
        "--backup-output", (Join-Path $RepositoryRoot "data\backups")
    )
    & $UvCommand @Arguments 1>> $OutputLog 2>> $ErrorLog
    if ($LASTEXITCODE -ne 0) {
        $FailedAt = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
        Add-Content -LiteralPath $ErrorLog -Value "[$FailedAt] 每日流程失敗，退出碼：$LASTEXITCODE"
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

$CompletedAt = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
Add-Content -LiteralPath $OutputLog -Value "[$CompletedAt] 每日流程完成"
