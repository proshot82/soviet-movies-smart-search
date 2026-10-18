
@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting film search... the browser opens by itself when the server is ready.
python film_search.py serve --port 8080
pause
 