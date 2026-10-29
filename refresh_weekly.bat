@echo off
python "%~dp0code\clean_and_refresh.py"
if errorlevel 1 exit /b 1
python "%~dp0code\build_dashboard_data.py"
if errorlevel 1 exit /b 1
echo Local data and dashboard refreshed. Website publication is separate.
