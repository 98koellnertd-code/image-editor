# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('constants.py', '.'), ('layers.py', '.'), ('effects.py', '.'), ('dialogs.py', '.'), ('icon.ico', '.')]
binaries = []
hiddenimports = ['PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont', 'PIL.ImageTk', 'PIL.ImageFilter', 'PIL.ImageEnhance', 'PIL.ImageOps', 'PIL.ImageChops', 'tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.filedialog', 'tkinter.simpledialog', 'tkinter.colorchooser']

# Alle optionalen Pakete fest ins exe einbacken, damit SVG/PSD/Zauberstab/KI
# OHNE separate Installation funktionieren. Fehlende Pakete werden uebersprungen,
# damit der Build nicht abbricht, wenn eins davon nicht installiert ist.
# Hinweis: SVG laeuft ueber PyMuPDF (fitz). cairosvg/svglib/reportlab sind nur
# optionale Fallbacks und unter Windows ohne native Cairo-DLL nicht nutzbar –
# daher hier bewusst NICHT gelistet, um Build-Warnungen zu vermeiden.
_optional = ['PIL', 'fitz', 'rembg',
             'psd_tools', 'numpy', 'scipy']
for _pkg in _optional:
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d; binaries += _b; hiddenimports += _h
    except Exception as _e:
        print(f'[spec] optionales Paket uebersprungen: {_pkg} ({_e})')


a = Analysis(
    ['image_editor.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ImageEditorPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
