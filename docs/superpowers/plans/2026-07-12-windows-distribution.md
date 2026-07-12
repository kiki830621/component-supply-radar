# Native Windows Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Component Supply Radar installable and operable by a non-developer on native Windows 10 or 11 without a preinstalled Python runtime.

**Architecture:** PowerShell entry points derive the repository root from their own location and delegate Python/runtime management to the locked `uv` project. A Windows Scheduled Task calls one stable daily wrapper, while local DuckDB remains authoritative and MotherDuck remains an optional one-way copy. Windows CI executes the same frozen installation and offline quickstart documented for users.

**Tech Stack:** Windows PowerShell 5.1+, uv, Python 3.12, DuckDB, Typer, pytest, Ruff, mypy, Windows Task Scheduler, GitHub Actions.

## Global Constraints

- Official platform is native Windows 10 or Windows 11; no WSL is required.
- The user does not need a preinstalled Python interpreter.
- Runtime dependencies come from `pyproject.toml` and `uv.lock`; user installation uses `uv sync --frozen --no-dev`.
- Developer installation uses `uv sync --frozen --all-groups`.
- Installation and scheduling use the current user and do not require administrator rights.
- Existing `.env`, `data\`, `reports\`, `work\`, DuckDB, logs, backups, and real watchlists are never deleted or overwritten by installation.
- API keys and tokens never appear in Git, scheduled-task arguments, or ordinary log output.
- Future Electronics is the only automated distributor source. No Mouser or webpage scraper is introduced.
- CI and offline self-checks never call Future Electronics or MotherDuck and require no secrets.

---

## File Map

- `.python-version`: requests the Python 3.12 series from uv.
- `.github/workflows/ci.yml`: validates the locked project and offline quickstart on Windows.
- `scripts/common.ps1`: shared strict-mode, repository-root, command and exit-code helpers.
- `scripts/install.ps1`: idempotent runtime setup and offline installation check.
- `scripts/run_daily.ps1`: stable scheduled-task target and log writer.
- `scripts/install_scheduled_task.ps1`: creates or updates the current-user daily task.
- `scripts/scheduled_task_status.ps1`: reports whether the task exists and its run state.
- `scripts/uninstall_scheduled_task.ps1`: removes only this project's task.
- `scripts/open_latest_report.ps1`: opens the newest generated HTML report.
- `tests/test_windows_scripts.py`: static and dry-run contracts for Windows scripts.
- `tests/test_readme_windows.py`: keeps documented Windows commands, data locations and scope synchronized.
- `README.md`: Windows-first operator handbook.
- `docs/superpowers/specs/2026-07-11-component-supply-radar-design.md`: historical notice pointing to current Future-only and Windows contracts.
- `docs/superpowers/plans/2026-07-11-component-supply-radar.md`: historical notice preventing obsolete Mouser/macOS instructions from being treated as current.

### Task 1: Lock the Windows runtime contract

**Files:**
- Create: `.python-version`
- Modify: `pyproject.toml`
- Test: `tests/test_windows_scripts.py`

**Interfaces:**
- Produces: a Python 3.12 request readable by uv and package metadata declaring Windows support.

- [ ] **Step 1: Write failing metadata tests**

```python
from pathlib import Path
import tomllib

ROOT = Path(__file__).parents[1]


def test_python_version_requests_312() -> None:
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"


def test_package_declares_windows_support() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert "Operating System :: Microsoft :: Windows :: Windows 10" in project["classifiers"]
    assert "Operating System :: Microsoft :: Windows :: Windows 11" in project["classifiers"]
```

- [ ] **Step 2: Run `uv run pytest tests/test_windows_scripts.py -q`**

Expected: FAIL because `.python-version` and Windows classifiers do not exist.

- [ ] **Step 3: Add `.python-version` containing `3.12` and the two Windows classifiers to `pyproject.toml`**
- [ ] **Step 4: Run the test and confirm it passes, then run `uv lock --check`**

Expected: metadata tests PASS and the lockfile is current.

### Task 2: Add reusable PowerShell foundations and an idempotent installer

**Files:**
- Create: `scripts/common.ps1`
- Create: `scripts/install.ps1`
- Modify: `tests/test_windows_scripts.py`

**Interfaces:**
- Produces: `Get-RepositoryRoot`, `Invoke-CheckedCommand`, `Get-UvCommand`, and `install.ps1 -SkipUvInstall -SkipSelfCheck -WhatIf`.
- Consumes: repository `pyproject.toml`, `uv.lock`, `.env.example`, sample CSV, and existing CLI.

- [ ] **Step 1: Write failing script contract tests**

```python
def script(name: str) -> str:
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_installer_is_idempotent_and_uses_frozen_runtime_dependencies() -> None:
    body = script("install.ps1")
    assert "Set-StrictMode -Version Latest" in body
    assert "$PSScriptRoot" in body
    assert "uv sync --frozen --no-dev" in body
    assert "Test-Path -LiteralPath $EnvironmentFile" in body
    assert "Copy-Item" in body
    assert "RADAR_DATABASE=data/radar.duckdb" not in body


def test_installer_has_safe_preview_and_self_check_switches() -> None:
    body = script("install.ps1")
    assert "[switch]$WhatIf" in body
    assert "[switch]$SkipUvInstall" in body
    assert "[switch]$SkipSelfCheck" in body
    assert "work\\install-check.duckdb" in body
```

- [ ] **Step 2: Run the two tests and verify missing-file failures**
- [ ] **Step 3: Implement `common.ps1`**

The shared script must set strict mode, stop on errors, derive the repository root with `Split-Path -Parent $PSScriptRoot`, locate `uv.exe` using `Get-Command`, and wrap native commands so a nonzero `$LASTEXITCODE` throws with the command name.

- [ ] **Step 4: Implement `install.ps1`**

The installer must:

1. reject non-Windows hosts;
2. verify `pyproject.toml`, `uv.lock`, `.env.example`, and the example CSV;
3. install `uv` with `winget install --id astral-sh.uv -e --accept-package-agreements --accept-source-agreements` only when missing and not skipped;
4. refresh the process PATH and fail with the official manual instruction if `uv` remains unavailable;
5. run `uv python install 3.12` and `uv sync --frozen --no-dev`;
6. create `.env` only when absent;
7. create `data`, `data\backups`, `data\logs`, `reports`, and `work`;
8. initialize `data\radar.duckdb`;
9. unless skipped, create a disposable `work\install-check.duckdb`, import the example CSV, analyze it, and render `work\install-check-report`;
10. never delete or replace user files; and
11. make `-WhatIf` print planned operations without mutation.

- [ ] **Step 5: Run the focused tests, then run `uv run ruff check tests/test_windows_scripts.py`**

Expected: PASS.

### Task 3: Add Windows daily operation and Scheduled Task management

**Files:**
- Create: `scripts/run_daily.ps1`
- Create: `scripts/install_scheduled_task.ps1`
- Create: `scripts/scheduled_task_status.ps1`
- Create: `scripts/uninstall_scheduled_task.ps1`
- Create: `scripts/open_latest_report.ps1`
- Modify: `tests/test_windows_scripts.py`

**Interfaces:**
- Produces: scheduled task `ComponentSupplyRadar-Daily`, default time `07:30`, stable wrapper command, queryable status, safe removal, and latest-report opening.
- Consumes: `common.ps1`, installed `.venv`, `.env`, and `component-supply-radar run-daily`.

- [ ] **Step 1: Write failing contracts for task name, current-user logon, path safety and preview support**

```python
def test_scheduler_scripts_share_one_task_name_and_support_preview() -> None:
    for name in (
        "install_scheduled_task.ps1",
        "scheduled_task_status.ps1",
        "uninstall_scheduled_task.ps1",
    ):
        body = script(name)
        assert "ComponentSupplyRadar-Daily" in body
    assert "[switch]$WhatIf" in script("install_scheduled_task.ps1")
    assert "[switch]$WhatIf" in script("uninstall_scheduled_task.ps1")


def test_daily_wrapper_uses_repository_root_and_separate_logs() -> None:
    body = script("run_daily.ps1")
    assert "$PSScriptRoot" in body
    assert "component-supply-radar" in body
    assert "run-daily" in body
    assert "daily-output.log" in body
    assert "daily-error.log" in body
```

- [ ] **Step 2: Run the tests and verify the scripts are missing**
- [ ] **Step 3: Implement the five scripts**

Use the `ScheduledTasks` PowerShell module. Register the task with an action that runs `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <quoted absolute run_daily.ps1>`, a daily trigger at 07:30, and an interactive current-user principal so no password is stored. Set the working directory inside `run_daily.ps1`, not in the task action. Status returns a nonzero code only for actual query errors; an absent task is reported clearly. Removal of an absent task succeeds.

- [ ] **Step 4: Add a parser test when `pwsh` or Windows PowerShell is available**

The pytest test conditionally locates `pwsh` or `powershell`; for every `.ps1`, run the PowerShell parser API and assert zero parse errors. On non-Windows machines without PowerShell, mark only this parser test skipped; static contracts still run.

- [ ] **Step 5: Run `uv run pytest tests/test_windows_scripts.py -q`**

Expected: all static contracts pass; parser test either passes or is explicitly skipped when PowerShell is unavailable.

### Task 4: Rewrite the Windows-first operator handbook and align historical notes

**Files:**
- Modify: `README.md`
- Create: `tests/test_readme_windows.py`
- Modify: `docs/superpowers/specs/2026-07-11-component-supply-radar-design.md`
- Modify: `docs/superpowers/plans/2026-07-11-component-supply-radar.md`

**Interfaces:**
- Produces: a single Windows-first install/run/update/uninstall handbook whose commands match the scripts.
- Consumes: all scripts from Tasks 2 and 3 and the actual CLI command names.

- [ ] **Step 1: Write failing README consistency tests**

```python
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_is_windows_first_and_documents_installation() -> None:
    assert "Windows 10" in README and "Windows 11" in README
    assert ".\\scripts\\install.ps1" in README
    assert "uv sync --frozen --no-dev" in README
    assert ".\\scripts\\install_scheduled_task.ps1" in README
    assert ".\\scripts\\scheduled_task_status.ps1" in README
    assert ".\\scripts\\uninstall_scheduled_task.ps1" in README


def test_readme_documents_every_local_and_cloud_location() -> None:
    for value in (
        "data\\radar.duckdb",
        "data\\backups",
        "data\\logs",
        "reports",
        ".env",
        "component_supply_radar",
    ):
        assert value in README


def test_readme_does_not_claim_mouser_or_web_scraping_support() -> None:
    assert "Future Electronics 是唯一自動化" in README
    assert "不包含 Mouser 自動收集" in README
    assert "不包含網頁爬取" in README
```

- [ ] **Step 2: Run `uv run pytest tests/test_readme_windows.py -q` and verify failures against the current macOS README**
- [ ] **Step 3: Rewrite `README.md` in Taiwan Traditional Chinese**

Include: purpose and non-investment disclaimer; authorization boundary; Windows 10/11 prerequisites; repository/ZIP acquisition; one-command PowerShell install; what the installer changes; install verification; exact data locations; `.env`; Future API; watchlist; offline CSV; first live collection; report generation/opening; scheduling install/status/manual run/removal; MotherDuck; backups/restore concept; size estimate; updates; uninstall without accidental data loss; all CLI commands; troubleshooting; developer checks; and official reference links.

- [ ] **Step 4: Add a superseded notice to the two 2026-07-11 historical documents**

The notice must state that Windows distribution is defined by `2026-07-12-windows-distribution-design.md`, automated ingestion is Future-only, and the historical Mouser/macOS plan must not be implemented.

- [ ] **Step 5: Run README tests and search for contradictory active documentation**

Run:

```powershell
uv run pytest tests/test_readme_windows.py -q
rg -n "macOS 桌機|Mouser adapter|mouser-live|launchd 每日" README.md docs openspec
```

Expected: tests PASS; any matches occur only inside an explicitly superseded historical section or historical quotation.

### Task 5: Validate on a clean Windows GitHub Actions runner

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `tests/test_windows_scripts.py`

**Interfaces:**
- Produces: pull-request and push checks for frozen sync, complete quality gates and the documented offline quickstart on `windows-latest`.

- [ ] **Step 1: Write a failing workflow contract test**

```python
def test_windows_ci_runs_locked_install_and_offline_quickstart() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "windows-latest" in workflow
    assert "uv sync --frozen --all-groups" in workflow
    assert "uv run pytest -q" in workflow
    assert "uv run ruff check ." in workflow
    assert "uv run ruff format --check ." in workflow
    assert "uv run mypy src" in workflow
    assert "install.ps1 -SkipUvInstall" in workflow
```

- [ ] **Step 2: Run the focused test and confirm the workflow is missing**
- [ ] **Step 3: Implement `.github/workflows/ci.yml`**

Use `actions/checkout`, Astral's official `setup-uv` action with lockfile caching, and a `windows-latest` job. Run frozen developer sync, pytest, Ruff, formatting, mypy, CLI help, and `install.ps1 -SkipUvInstall`. Upload the offline HTML/CSV report only on failure; never configure secrets or live API calls.

- [ ] **Step 4: Run all local workflow/static tests**

Expected: PASS.

### Task 6: Full acceptance and handoff

**Files:**
- Modify only files required by failures found in this task.

- [ ] **Step 1: Recreate the local environment from the lock contract**

Run: `uv sync --frozen --all-groups`

Expected: exit 0.

- [ ] **Step 2: Run the complete quality gate**

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run component-supply-radar --help
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 3: Run the offline end-to-end flow in a path containing spaces**

Create an ignored temporary directory under `work/windows install check`, initialize a disposable DuckDB, import `examples/supplier-observations.csv`, analyze it, render an HTML/CSV report, and verify both files exist. Do not call Future or MotherDuck.

- [ ] **Step 4: Run scope and secret scans**

Confirm there is no Mouser provider, webpage scraper, Supabase dependency, committed `.env`, API key, DuckDB, Parquet, log or generated report. Confirm `git status --short` contains only intentional project sources and pre-existing files.

- [ ] **Step 5: Review README command-by-command against script and CLI names**

Every operator command, path, task name and default time must match the implemented files. Record the platform limitation if native Windows execution cannot be performed locally; use the Windows Actions job as the definitive clean-host check after push.
