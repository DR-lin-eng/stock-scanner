# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('D:\\Users\\admin\\Desktop\\股票分析\\3.0 webapp（支持港股美股）\\.build_temp\\config_sample.json', '.')]
hiddenimports = ['openai', 'anthropic', 'zhipuai', 'numpy._core._exceptions']
datas += collect_data_files('akshare')
hiddenimports += collect_submodules('numpy._core')


a = Analysis(
    ['desktop_gui_launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'tensorflow', 'paddle', 'cv2', 'scipy', 'sklearn', 'matplotlib', 'nltk', 'transformers', 'bitsandbytes', 'onnxruntime', 'PyQt5', 'PyQt6', 'PySide6', 'pygame', 'librosa', 'soundfile', 'datasets', 'fugashi', 'numba', 'sympy', 'sphinx'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='StockAnalyzerDesktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='StockAnalyzerDesktop',
)
