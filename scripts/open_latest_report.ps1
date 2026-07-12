Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "common.ps1")

$ReportDirectory = Join-Path (Get-RepositoryRoot) "reports"
$LatestReport = Get-ChildItem -LiteralPath $ReportDirectory -Filter "*.html" -File `
    -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if ($null -eq $LatestReport) {
    throw "尚未找到 HTML 報告。請先執行 scripts\run_daily.ps1。"
}

Start-Process -FilePath $LatestReport.FullName
