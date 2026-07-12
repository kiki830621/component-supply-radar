param(
    [ValidatePattern("^([01]\d|2[0-3]):[0-5]\d$")]
    [string]$At = "07:30",
    [switch]$WhatIf
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "common.ps1")

$TaskName = "ComponentSupplyRadar-Daily"
$RepositoryRoot = Get-RepositoryRoot
$DailyScript = Join-Path $RepositoryRoot "scripts\run_daily.ps1"
$EnvironmentFile = Join-Path $RepositoryRoot ".env"
if (-not (Test-Path -LiteralPath $DailyScript -PathType Leaf)) {
    throw "找不到每日執行腳本：$DailyScript"
}
if (-not (Test-Path -LiteralPath $EnvironmentFile -PathType Leaf)) {
    throw "尚未完成安裝：找不到 .env。請先執行 scripts\install.ps1。"
}

$PowerShellPath = (Get-Command -Name powershell.exe -ErrorAction Stop).Source
$ActionArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$DailyScript`""
$RunAt = [DateTime]::ParseExact($At, "HH:mm", [Globalization.CultureInfo]::InvariantCulture)
$CurrentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name

if ($WhatIf) {
    Write-Host "預覽：將為 $CurrentUser 建立或更新工作 $TaskName，每天 $At 執行："
    Write-Host "$PowerShellPath $ActionArguments"
    exit 0
}

$Action = New-ScheduledTaskAction -Execute $PowerShellPath -Argument $ActionArguments
$Trigger = New-ScheduledTaskTrigger -Daily -At $RunAt
$Principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Principal $Principal -Settings $Settings -Description "每日執行 Component Supply Radar" `
    -Force | Out-Null

Write-Host "已安裝每日 $At 工作：$TaskName"
