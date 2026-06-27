# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('modules', 'modules'),
    ],
    hiddenimports=[
        'httpx',
        'httpx._transports.default',
        'httpcore._backends.anyio',
        'httpcore._backends.sync',
        'sniffio',
        'anyio',
        'fastapi',
        'uvicorn',
        'python_dotenv',
        'loguru',
        'aiofiles',
    ],
    collect_submodules=[],
    collect_binaries=[],
    collect_data_files=[],
    collect_dynamic_libs=[],
    exclude_modules=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ptaf-tools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
