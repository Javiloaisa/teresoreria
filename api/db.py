"""Conexión a Postgres.

Un pool pequeño y perezoso. Podría parecer excesivo para una app de un solo
usuario, pero es al revés: `construir_resumen()` lanza cinco consultas y se
llama en cada alta de gasto, así que abrir una conexión por consulta multiplica
por cinco el coste de la pantalla más usada.

Las filas salen como diccionarios (`dict_row`) y los NUMERIC como `Decimal`,
que es justo lo que espera `calc.py`.
"""

import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "Falta la variable de entorno DATABASE_URL "
            "(la cadena de conexión a Postgres)."
        )
    return dsn


def pool() -> ConnectionPool:
    """El pool se crea en la primera consulta, no al importar el módulo: así
    `manage.py` y los tests puros pueden cargar esto sin base de datos delante.
    """
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            _dsn(),
            min_size=1,
            max_size=4,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


@contextmanager
def get_conn():
    """Una conexión del pool. Commit al salir bien, rollback si algo falla."""
    with pool().connection() as conn:
        yield conn


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Atajo de solo lectura: devuelve todas las filas."""
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql: str, params: tuple = ()) -> dict | None:
    with get_conn() as conn:
        return conn.execute(sql, params).fetchone()
