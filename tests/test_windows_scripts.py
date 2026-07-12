from __future__ import annotations

import codecs
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def script(name: str) -> str:
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_powershell_scripts_use_utf8_bom_for_windows_powershell_51() -> None:
    for path in sorted((ROOT / "scripts").glob("*.ps1")):
        assert path.read_bytes().startswith(codecs.BOM_UTF8), path.name


def test_python_version_requests_312() -> None:
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"


def test_installer_environment_template_is_tracked_by_git() -> None:
    completed = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env.example"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_package_declares_windows_support() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    classifiers = project["classifiers"]
    assert "Operating System :: Microsoft :: Windows :: Windows 10" in classifiers
    assert "Operating System :: Microsoft :: Windows :: Windows 11" in classifiers


def test_windows_runtime_installs_iana_timezone_data() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert any(
        dependency.startswith("tzdata") and "platform_system == 'Windows'" in dependency
        for dependency in project["dependencies"]
    )


def test_installer_is_idempotent_and_uses_frozen_runtime_dependencies() -> None:
    body = script("install.ps1")
    assert "Set-StrictMode -Version Latest" in body
    assert "$PSScriptRoot" in body
    assert '"sync", "--frozen", "--no-dev"' in body
    assert "Test-Path -LiteralPath $EnvironmentFile" in body
    assert "Copy-Item" in body
    assert "RADAR_DATABASE=data/radar.duckdb" not in body


def test_installer_has_safe_preview_and_self_check_switches() -> None:
    body = script("install.ps1")
    assert "[switch]$WhatIf" in body
    assert "[switch]$SkipUvInstall" in body
    assert "[switch]$SkipSelfCheck" in body
    assert '"work\\install-check.duckdb"' in body


def test_installer_preserves_a_user_watchlist_and_daily_run_uses_it() -> None:
    installer = script("install.ps1")
    daily = script("run_daily.ps1")
    assert "$WatchlistFile" in installer
    assert "Test-Path -LiteralPath $WatchlistFile" in installer
    assert "data\\watchlist.csv" in installer
    assert '"--watchlist", $WatchlistFile' in daily


def test_common_script_checks_native_exit_codes() -> None:
    body = script("common.ps1")
    assert "Set-StrictMode -Version Latest" in body
    assert "$LASTEXITCODE" in body
    assert "Get-Command -Name uv" in body
    assert "Split-Path -Parent $PSScriptRoot" in body


def test_windows_commands_force_python_utf8_mode() -> None:
    assert '$env:PYTHONUTF8 = "1"' in script("common.ps1")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert 'PYTHONUTF8: "1"' in workflow


def test_scheduler_scripts_share_one_task_name_and_support_preview() -> None:
    for name in (
        "install_scheduled_task.ps1",
        "scheduled_task_status.ps1",
        "uninstall_scheduled_task.ps1",
    ):
        assert "ComponentSupplyRadar-Daily" in script(name)
    assert "[switch]$WhatIf" in script("install_scheduled_task.ps1")
    assert "[switch]$WhatIf" in script("uninstall_scheduled_task.ps1")


def test_scheduler_uses_current_user_without_storing_a_password() -> None:
    body = script("install_scheduled_task.ps1")
    assert "New-ScheduledTaskPrincipal" in body
    assert "-LogonType Interactive" in body
    assert "-RunLevel Limited" in body
    assert "Register-ScheduledTask" in body
    assert "-Password" not in body


def test_daily_wrapper_uses_repository_root_and_separate_logs() -> None:
    body = script("run_daily.ps1")
    assert "$PSScriptRoot" in body
    assert "component-supply-radar" in body
    assert '"run-daily"' in body
    assert "daily-output.log" in body
    assert "daily-error.log" in body


def test_report_opener_uses_windows_shell() -> None:
    body = script("open_latest_report.ps1")
    assert "Start-Process" in body
    assert "*.html" in body


def test_windows_ci_runs_locked_install_and_offline_quickstart() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "windows-latest" in workflow
    assert "uv sync --frozen --all-groups" in workflow
    assert "uv run pytest -q" in workflow
    assert "uv run ruff check ." in workflow
    assert "uv run ruff format --check ." in workflow
    assert "uv run mypy src" in workflow
    assert "install.ps1 -SkipUvInstall" in workflow
    assert "FUTURE_API_KEY" not in workflow
    assert "MOTHERDUCK_TOKEN" not in workflow


def test_powershell_scripts_parse_when_a_runtime_is_available() -> None:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell is unavailable on this non-Windows verification host")
    command = (
        "$errors = $null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:CSR_SCRIPT_TO_PARSE, [ref]$null, [ref]$errors) | Out-Null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
    )
    for path in sorted((ROOT / "scripts").glob("*.ps1")):
        completed = subprocess.run(
            [executable, "-NoProfile", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "CSR_SCRIPT_TO_PARSE": str(path)},
        )
        assert completed.returncode == 0, f"{path.name}: {completed.stderr}"
