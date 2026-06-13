@echo off
title Image Editor Pro
cd /d "%~dp0"

python -c "import PIL" 2>nul
if errorlevel 1 (
    echo Installiere Pillow...
    pip install Pillow
)

python image_editor.py
pause
