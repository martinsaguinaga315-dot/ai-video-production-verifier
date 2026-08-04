from pathlib import Path


def test_build_script_discovers_iscc_without_hardcoding_custom_paths():
    script = Path("packaging/build_windows.ps1").read_text(encoding="utf-8")
    assert "function Find-IsccExecutable" in script
    assert "Get-Command ISCC.exe" in script
    assert "$env:LOCALAPPDATA" in script
    assert "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*" in script
    assert "HKCU:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*" in script
    assert "HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*" in script
    assert "HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*" in script
    assert "DisplayName -match '^Inno Setup'" in script
    assert "Using Inno Setup compiler:" in script
    assert "Installer is required for this release build" in script
    assert "SkipInstaller" not in script
    assert "E:\\1导演测试程序位置" not in script
