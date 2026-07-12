Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TaskName = "ComponentSupplyRadar-Daily"
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $Task) {
    Write-Host "尚未安裝工作：$TaskName"
    exit 0
}

$Info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
[PSCustomObject]@{
    TaskName = $TaskName
    State = $Task.State
    LastRunTime = $Info.LastRunTime
    LastTaskResult = $Info.LastTaskResult
    NextRunTime = $Info.NextRunTime
} | Format-List
