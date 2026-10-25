#!/bin/bash
# doble clic en Finder abre Ming Studio
cd "$(dirname "$0")" || exit 1
[ -d .venv ] || { echo " Primero corre: bash instalar.sh"; exit 1; }
.venv/bin/python server.py --abrir
