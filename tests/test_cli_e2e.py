from pathlib import Path

from typer.testing import CliRunner

from component_supply_radar.cli import app
from component_supply_radar.models import Observation, PanelMember

RUNNER = CliRunner()
EXAMPLE = Path(__file__).parents[1] / "examples" / "supplier-observations.csv"


def test_demo_csv_to_html_report(tmp_path: Path) -> None:
    database = tmp_path / "radar.duckdb"
    reports = tmp_path / "reports"

    imported = RUNNER.invoke(
        app,
        ["--database", str(database), "import-csv", str(EXAMPLE)],
    )
    analyzed = RUNNER.invoke(app, ["--database", str(database), "analyze"])
    reported = RUNNER.invoke(
        app,
        ["--database", str(database), "report", "--output", str(reports)],
    )

    assert imported.exit_code == 0, imported.output
    assert "匯入 3 筆觀測" in imported.output
    assert analyzed.exit_code == 0, analyzed.output
    assert "更新 1 個分類訊號" in analyzed.output
    assert reported.exit_code == 0, reported.output
    assert (reports / "latest.html").exists()
    assert (reports / "latest.csv").exists()


def test_cli_exposes_required_commands() -> None:
    result = RUNNER.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in (
        "init-db",
        "import-csv",
        "collect-future",
        "analyze",
        "report",
        "sync",
        "backup",
        "run-daily",
    ):
        assert command in result.output


def test_collect_future_without_key_fails_loudly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("FUTURE_API_KEY", raising=False)

    result = RUNNER.invoke(
        app,
        ["--database", str(tmp_path / "radar.duckdb"), "collect-future"],
    )

    assert result.exit_code != 0
    assert "FUTURE_API_KEY" in result.output


def test_run_daily_collects_when_key_exists_and_creates_due_backup(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[int] = []

    class FakeFutureClient:
        source_id = "future"
        last_request_count = 0

        def __init__(self, api_key: str) -> None:
            assert api_key == "issued-key"

        def collect(self, members: list[PanelMember], observed_at_utc) -> tuple[Observation, ...]:
            self.last_request_count = 1
            calls.append(len(members))
            return ()

    monkeypatch.setenv("FUTURE_API_KEY", "issued-key")
    monkeypatch.delenv("MOTHERDUCK_TOKEN", raising=False)
    monkeypatch.setattr("component_supply_radar.cli.FutureClient", FakeFutureClient)
    database = tmp_path / "radar.duckdb"
    backups = tmp_path / "backups"

    result = RUNNER.invoke(
        app,
        [
            "--database",
            str(database),
            "run-daily",
            "--backup-output",
            str(backups),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [2]
    assert "Future 收集狀態" in result.output
    assert len(list(backups.glob("*/manifest.json"))) == 1
