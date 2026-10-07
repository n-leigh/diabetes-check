from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPEC).resolve().parents[2]
hiddenimports = collect_submodules("sqlcipher3") + [
    "sklearn.calibration",
    "sklearn.ensemble._gb",
]

a = Analysis(
    [str(project_root / "wsgi.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "templates"), "templates"),
        (str(project_root / "static"), "static"),
        (str(project_root / "model"), "model"),
        (str(project_root / "packaging" / "windows" / "verify_sqlcipher_bundle.py"), "packaging/windows"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, name="DiaBeates", console=True)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="DiaBeates",
)