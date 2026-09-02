"""Carga el .env de desarrollo para los tests que tocan la base de datos.

Los tests de `calc.py` y `clasificar.py` no necesitan nada de esto: son puros.
Los de la API se saltan solos si no hay DATABASE_URL (por ejemplo en el CI).
"""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def pytest_configure():
    env = RAIZ / ".env"
    if not env.exists():
        return
    for linea in env.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip())
