"""Comandos de gestión.

    python manage.py set-password

Crea (o cambia) la contraseña del único usuario. En el servidor:

    docker compose exec api python manage.py set-password
"""

import getpass
import sys

from auth import hash_password
from db import get_conn


def pedir_password(mensaje: str) -> str:
    """Pide la contraseña sin que se vea, o la lee de la entrada estándar.

    `getpass` habla con la consola directamente, así que se cuelga cuando no
    hay terminal: por ejemplo con `docker compose exec -T` o desde un script.
    En ese caso se lee de stdin, que es lo que el que llama espera.
    """
    if sys.stdin.isatty():
        return getpass.getpass(mensaje)
    print(mensaje, end="", flush=True)
    return sys.stdin.readline().rstrip("\n")


def set_password() -> int:
    password = pedir_password("Contraseña nueva: ")
    if len(password) < 8:
        print("Demasiado corta: mínimo 8 caracteres.", file=sys.stderr)
        return 1
    if password != pedir_password("Repítela: "):
        print("No coinciden.", file=sys.stderr)
        return 1

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO usuario (id, password_hash) VALUES (1, %s)
            ON CONFLICT (id) DO UPDATE SET password_hash = EXCLUDED.password_hash
            """,
            (hash_password(password),),
        )
    print("Contraseña guardada.")
    return 0


COMANDOS = {"set-password": set_password}


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMANDOS:
        print(f"Uso: python manage.py [{' | '.join(COMANDOS)}]", file=sys.stderr)
        sys.exit(2)
    sys.exit(COMANDOS[sys.argv[1]]())
