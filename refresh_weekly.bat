@echo off
cd /d "%~dp0"
python -m dental_analytics.clean_and_refresh
if errorlevel 1 exit /b 1
python -m dental_analytics.build_dashboard_data
if errorlevel 1 exit /b 1
echo Local data and dashboard refreshed. Website publication is separate.
