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
python -c "import fitz" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] PyMuPDF nicht gefunden. Wird installiert...
    pip install pymupdf -q
)
python -c "import psd_tools" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] psd-tools nicht gefunden. Wird installiert...
    pip install psd-tools -q
)
python -c "import numpy, scipy" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] numpy/scipy nicht gefunden. Wird installiert...
    pip install numpy scipy -q
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

:: Kompilieren (ueber die .spec-Datei – dort werden ALLE optionalen Pakete
:: – PyMuPDF, cairosvg, rembg, psd-tools, numpy, scipy – fest eingebacken)
echo  [2/2] Kompiliere...
python -m PyInstaller --noconfirm "ImageEditorPro.spec"
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
