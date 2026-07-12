Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

function Get-RepositoryRoot {
    return Split-Path -Parent $PSScriptRoot
}

function Get-UvCommand {
    $Command = Get-Command -Name uv -ErrorAction SilentlyContinue
    if ($null -eq $Command) {
        return $null
    }
    return $Command.Source
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$DisplayName
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$DisplayName 失敗，退出碼：$LASTEXITCODE"
    }
}

function Update-ProcessPath {
    $MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $Separator = [IO.Path]::PathSeparator
    $env:Path = "$MachinePath$Separator$UserPath"
}
