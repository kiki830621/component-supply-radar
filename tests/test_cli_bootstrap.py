from typer.testing import CliRunner

from component_supply_radar.cli import app


def test_package_bootstrap(monkeypatch) -> None:
    monkeypatch.delenv("FUTURE_API_KEY", raising=False)
    monkeypatch.delenv("MOTHERDUCK_TOKEN", raising=False)

    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "電子零件供應壓力研究工具" in result.stdout
