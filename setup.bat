@echo off
title SnowDesk Setup
echo Installing SnowDesk dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Setup complete! Double-click SnowDesk.vbs to launch silently.
pause
