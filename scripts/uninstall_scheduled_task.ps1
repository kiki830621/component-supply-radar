param(
    [switch]$WhatIf
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TaskName = "ComponentSupplyRadar-Daily"
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $Task) {
    Write-Host "工作不存在，不需要移除：$TaskName"
    exit 0
}

if ($WhatIf) {
    Write-Host "預覽：將移除工作 $TaskName；程式與 data 資料不會刪除。"
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
Write-Host "已移除工作：$TaskName；程式與 data 資料均保留。"
