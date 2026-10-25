#!/bin/bash
# Ming Studio: instalador para Mac (y Linux)
cd "$(dirname "$0")" || exit 1
set -e
echo
echo " === Ming Studio: instalando (unos 5 minutos, no cierres esta ventana) ==="
echo
falta() { echo " Falta $1. $2"; exit 1; }
command -v python3 >/dev/null || falta "Python 3.10 o mas nuevo" "Bajalo en https://www.python.org/downloads/"
command -v node >/dev/null || falta "Node.js" "Bajalo en https://nodejs.org (version LTS)"
command -v git >/dev/null || falta "Git" "En Mac corre: xcode-select --install"

echo " [1/4] Preparando Python..."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
echo " [2/4] Bajando las piezas de Python (unos 150 MB, es el paso mas largo)..."
.venv/bin/python -m pip install -r requirements.txt
echo " [3/4] Instalando el exportador..."
npm install --silent
echo " [4/4] Bajando Chromium para exportar (si ya lo tienes, es rapido)..."
npx playwright install chromium
chmod +x iniciar.command

echo
echo " === Listo. Abre Ming Studio con doble clic en iniciar.command ==="
