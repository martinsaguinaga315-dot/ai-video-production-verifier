# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files
from app_version import APP_NAME

ROOT = Path(SPECPATH).parent
datas = [(str(ROOT / "assets"), "assets"), (str(ROOT / "examples"), "examples"), (str(ROOT / "LICENSE"), ".")]
datas += collect_data_files("customtkinter")
a = Analysis([str(ROOT / "desktop_app.py")], pathex=[str(ROOT)], binaries=[], datas=datas, hiddenimports=["keyring.backends.Windows", "importlib_metadata", "docx", "dotenv", "openai"], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=["pytest", "tests"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP_NAME, console=False, icon=str(ROOT / "assets" / "app.ico"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)
