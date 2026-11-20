@echo off
cd /d "%~dp0"
python -m pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name "SnowDesk" main.py
echo.
echo Build finished! Check dist\SnowDesk\SnowDesk.exe
pause
