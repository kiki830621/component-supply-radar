import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_repository_uses_mit_license_for_kiki830621() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("MIT License\n\nCopyright (c) 2026 kiki830621\n")
    assert "Permission is hereby granted, free of charge" in license_text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in license_text


def test_package_metadata_and_readme_declare_mit() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert "## 授權" in readme
    assert "[MIT License](LICENSE)" in readme
    assert "Copyright (c) 2026 kiki830621" in readme
