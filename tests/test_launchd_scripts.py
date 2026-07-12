import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
INSTALL = ROOT / "scripts" / "install_launchd.sh"
UNINSTALL = ROOT / "scripts" / "uninstall_launchd.sh"


def run(script: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "DRY_RUN": "1", "HOME": str(tmp_path)}
    return subprocess.run(
        ["zsh", str(script)],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_launchd_scripts_have_valid_shell_syntax() -> None:
    subprocess.run(["zsh", "-n", str(INSTALL)], check=True)
    subprocess.run(["zsh", "-n", str(UNINSTALL)], check=True)


def test_install_dry_run_renders_schedule_and_ignored_logs(tmp_path: Path) -> None:
    result = run(INSTALL, tmp_path)

    assert "<integer>7</integer>" in result.stdout
    assert "<integer>30</integer>" in result.stdout
    assert str(ROOT) in result.stdout
    assert str(ROOT / "data" / "logs") in result.stdout
    assert not (tmp_path / "Library" / "LaunchAgents").exists()


def test_uninstall_dry_run_does_not_remove_files(tmp_path: Path) -> None:
    agents = tmp_path / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    plist = agents / "com.component-supply-radar.daily.plist"
    plist.write_text("keep", encoding="utf-8")

    result = run(UNINSTALL, tmp_path)

    assert "DRY RUN" in result.stdout
    assert plist.exists()
