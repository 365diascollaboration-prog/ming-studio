@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  === Ming Studio: instalando (unos 5 minutos, no cierres esta ventana) ===
echo.
where python >nul 2>nul || (echo  Falta Python 3.10 o mas nuevo. Bajalo en https://www.python.org/downloads/ y marca "Add python.exe to PATH". & pause & exit /b 1)
where node >nul 2>nul || (echo  Falta Node.js. Bajalo en https://nodejs.org ^(version LTS^). & pause & exit /b 1)
where git >nul 2>nul || (echo  Falta Git. Bajalo en https://git-scm.com/download/win & pause & exit /b 1)

echo  [1/4] Preparando Python...
if not exist .venv python -m venv .venv || goto error
.venv\Scripts\python -m pip install -q --upgrade pip || goto error
echo  [2/4] Bajando las piezas de Python (unos 150 MB, es el paso mas largo)...
.venv\Scripts\python -m pip install -r requirements.txt || goto error
echo  [3/4] Instalando el exportador...
call npm install --silent || goto error
echo  [4/4] Bajando Chromium para exportar (si ya lo tienes, es rapido)...
call npx playwright install chromium || goto error

echo.
echo  === Listo. Abre Ming Studio con iniciar.bat ===
pause
exit /b 0

:error
echo.
echo  Algo fallo arriba. Copia el error y abre un issue en GitHub.
pause
exit /b 1
