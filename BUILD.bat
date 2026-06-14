@echo off
cd /d "%~dp0"
title Image Editor Pro - Build
echo.
echo  ==========================================
echo    Image Editor Pro
echo    Build-Prozess
echo  ==========================================
echo.

:: Abhaengigkeiten pruefen und ggf. installieren
echo  [PRE] Pruefe Abhaengigkeiten...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] PyInstaller nicht gefunden. Wird installiert...
    pip install pyinstaller -q
)
python -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Pillow nicht gefunden. Wird installiert...
    pip install Pillow -q
)
python -c "import rembg" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] rembg nicht gefunden. Wird installiert...
    pip install rembg -q
)
python -c "import cairosvg" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] cairosvg nicht gefunden. Wird installiert...
    pip install cairosvg -q
)

:: Laufende Instanz beenden (falls noch offen)
echo  [0/2] Laufende Instanz beenden (falls noetig)...
taskkill /f /im "ImageEditorPro.exe" >nul 2>&1
timeout /t 2 /nobreak >nul

:: Alten Build aufraeumen
echo  [1/2] Alte Build-Dateien loeschen...
if exist "dist\ImageEditorPro.exe" (
    del /f /q "dist\ImageEditorPro.exe"
    if exist "dist\ImageEditorPro.exe" (
        echo  [FEHLER] Datei gesperrt - bitte Programm manuell schliessen und nochmal starten.
        pause & exit /b 1
    )
)

:: Kompilieren
echo  [2/2] Kompiliere...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "ImageEditorPro" ^
    --icon "icon.ico" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL.Image" ^
    --hidden-import "PIL.ImageDraw" ^
    --hidden-import "PIL.ImageFont" ^
    --hidden-import "PIL.ImageTk" ^
    --hidden-import "PIL.ImageFilter" ^
    --hidden-import "PIL.ImageEnhance" ^
    --hidden-import "PIL.ImageOps" ^
    --hidden-import "PIL.ImageChops" ^
    --hidden-import "tkinter" ^
    --hidden-import "tkinter.ttk" ^
    --hidden-import "tkinter.messagebox" ^
    --hidden-import "tkinter.filedialog" ^
    --hidden-import "tkinter.simpledialog" ^
    --hidden-import "tkinter.colorchooser" ^
    --collect-all "PIL" ^
    --collect-all "rembg" ^
    --collect-all "cairosvg" ^
    --add-data "constants.py;." ^
    --add-data "layers.py;." ^
    --add-data "effects.py;." ^
    --add-data "dialogs.py;." ^
    --add-data "icon.ico;." ^
    image_editor.py
if errorlevel 1 (
    echo.
    echo  [FEHLER] Build fehlgeschlagen. Siehe Ausgabe oben.
    pause & exit /b 1
)

echo.
echo  ==========================================
echo  BUILD ERFOLGREICH
echo  Datei: dist\ImageEditorPro.exe
echo  ==========================================
echo.
pause
