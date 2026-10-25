@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (echo  Primero corre instalar.bat & pause & exit /b 1)
.venv\Scripts\python server.py --abrir
pause
