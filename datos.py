"""Carpeta de datos del usuario (marcas, series, biblioteca, memoria, disenos), fuera del codigo:
actualizar la app (git pull) nunca la toca. MING_DATOS la cambia (los tests usan una temporal)."""
import os
from pathlib import Path

DATOS = Path(os.environ.get("MING_DATOS") or Path.home() / "MingStudio")
DATOS.mkdir(parents=True, exist_ok=True)
