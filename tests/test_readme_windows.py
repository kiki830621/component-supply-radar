from pathlib import Path

ROOT = Path(__file__).parents[1]
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


def test_readme_documents_update_and_uninstall_data_safety() -> None:
    assert "更新程式" in README
    assert "解除安裝" in README
    assert "不會刪除資料" in README
