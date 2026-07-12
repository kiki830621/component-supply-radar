"""Command-line interface."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from component_supply_radar.analysis import latest_report_rows, refresh_category_signals
from component_supply_radar.backup import create_backup
from component_supply_radar.config import Settings
from component_supply_radar.pipeline import Collector
from component_supply_radar.policy import SourcePolicy
from component_supply_radar.providers.csv_import import read_observations_csv
from component_supply_radar.providers.future import FutureClient
from component_supply_radar.reporting import write_report
from component_supply_radar.storage import RadarRepository
from component_supply_radar.sync import SyncError, publish_to_motherduck
from component_supply_radar.watchlist import load_watchlist

app = typer.Typer(
    name="component-supply-radar",
    help="電子零件供應壓力研究工具",
    no_args_is_help=True,
)


@app.callback()
def main(
    context: typer.Context,
    database: Annotated[Path, typer.Option("--database")] = Path("data/radar.duckdb"),
) -> None:
    """Run Component Supply Radar commands."""
    context.obj = database


def _repository(context: typer.Context) -> RadarRepository:
    database = context.obj
    if not isinstance(database, Path):
        raise RuntimeError("database option was not initialized")
    return RadarRepository(database)


def _future_policy() -> SourcePolicy:
    return SourcePolicy(
        "future",
        True,
        True,
        0,
        True,
        date(2026, 7, 11),
        "https://www.futureelectronics.com/fr/api-solutions",
    )


def _csv_policy(source_id: str) -> SourcePolicy:
    return SourcePolicy(
        source_id,
        True,
        True,
        0,
        False,
        date.today(),
        "https://example.com/user-owned-data-terms",
    )


@app.command("init-db")
def init_db(context: typer.Context) -> None:
    repository = _repository(context)
    repository.initialize()
    typer.echo(f"已初始化 {repository.database_path}")


@app.command("import-csv")
def import_csv(
    context: typer.Context,
    path: Path,
    source_id: str = typer.Option("owned_csv", "--source-id"),
) -> None:
    repository = _repository(context)
    repository.initialize()
    observations = read_observations_csv(path, source_id)
    repository.save_observations(_csv_policy(source_id), observations)
    typer.echo(f"匯入 {len(observations)} 筆觀測")


@app.command("collect-future")
def collect_future(
    context: typer.Context,
    watchlist: Annotated[Path, typer.Option("--watchlist")] = Path("config/watchlist.example.csv"),
) -> None:
    settings = Settings.from_env()
    if settings.future_api_key is None:
        typer.echo("缺少 FUTURE_API_KEY，無法執行 Future 收集。", err=True)
        raise typer.Exit(2)
    repository = _repository(context)
    repository.initialize()
    members = load_watchlist(watchlist)
    result = Collector(repository).run(
        FutureClient(settings.future_api_key),
        _future_policy(),
        members,
        datetime.now(UTC),
    )
    typer.echo(f"Future 收集狀態：{result.status.value}")


@app.command("analyze")
def analyze(context: typer.Context) -> None:
    updated = refresh_category_signals(_repository(context))
    typer.echo(f"更新 {updated} 個分類訊號")


@app.command("report")
def report(
    context: typer.Context,
    output: Annotated[Path, typer.Option("--output")] = Path("reports"),
) -> None:
    settings = Settings.from_env()
    paths = write_report(latest_report_rows(_repository(context)), output, settings.timezone)
    typer.echo(f"報告：{paths[0]}、{paths[1]}")


@app.command("sync")
def sync(context: typer.Context) -> None:
    settings = Settings.from_env()
    repository = _repository(context)
    repository.initialize()
    try:
        result = publish_to_motherduck(
            repository,
            token=settings.motherduck_token,
            database_name=settings.motherduck_database,
        )
    except SyncError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(3) from error
    typer.echo("MotherDuck 同步略過" if result.status == "skipped" else "MotherDuck 同步完成")


@app.command("backup")
def backup(
    context: typer.Context,
    output: Annotated[Path, typer.Option("--output")] = Path("data/backups"),
) -> None:
    repository = _repository(context)
    repository.initialize()
    path = create_backup(repository, output, now=datetime.now(UTC))
    typer.echo(f"備份：{path}")


@app.command("run-daily")
def run_daily(
    context: typer.Context,
    output: Annotated[Path, typer.Option("--output")] = Path("reports"),
    watchlist: Annotated[Path, typer.Option("--watchlist")] = Path("config/watchlist.example.csv"),
    backup_output: Annotated[Path, typer.Option("--backup-output")] = Path("data/backups"),
) -> None:
    repository = _repository(context)
    repository.initialize()
    settings = Settings.from_env()
    if settings.future_api_key is None:
        typer.echo("Future 收集略過：未設定 FUTURE_API_KEY")
    else:
        result = Collector(repository).run(
            FutureClient(settings.future_api_key),
            _future_policy(),
            load_watchlist(watchlist),
            datetime.now(UTC),
        )
        typer.echo(f"Future 收集狀態：{result.status.value}")
    updated = refresh_category_signals(repository)
    write_report(latest_report_rows(repository), output, settings.timezone)
    sync_result = publish_to_motherduck(
        repository,
        token=settings.motherduck_token,
        database_name=settings.motherduck_database,
    )
    backup_status = "not-due"
    if _backup_is_due(backup_output, datetime.now(UTC)):
        create_backup(repository, backup_output, now=datetime.now(UTC))
        backup_status = "created"
    typer.echo(f"每日流程完成：{updated} 個分類；同步 {sync_result.status}")
    typer.echo(f"週備份：{backup_status}")


def _backup_is_due(root: Path, now: datetime) -> bool:
    manifests = sorted(root.glob("*/manifest.json")) if root.exists() else []
    if not manifests:
        return True
    try:
        payload = json.loads(manifests[-1].read_text(encoding="utf-8"))
        exported = datetime.fromisoformat(str(payload["exported_at_utc"]))
    except (KeyError, ValueError, json.JSONDecodeError):
        return True
    return exported <= now - timedelta(days=7)
