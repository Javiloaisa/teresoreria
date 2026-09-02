"""Recorrido completo por la API, contra una base de datos de verdad.

Es el guion de uso real: declarar el ingreso, dar de alta el seguro del coche,
apuntar la compra y registrar el cargo anual. Se salta solo si no hay
DATABASE_URL (el CI no tiene Postgres delante).

OJO: vacía las tablas de gastos, ingresos y recurrentes. Apuntar a la base de
desarrollo, nunca a la de producción.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="Necesita una base de datos (DATABASE_URL); en el CI no la hay.",
)

if os.environ.get("DATABASE_URL"):
    os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
    from fastapi.testclient import TestClient

    from auth import hash_password
    from db import get_conn
    from index import app

PASSWORD = "una-contrasena-de-prueba"


@pytest.fixture()
def cliente():
    with get_conn() as conn:
        conn.execute(
            "TRUNCATE gastos, ingresos, recurrentes, reglas RESTART IDENTITY CASCADE")
        # Reglas propias en vez de las que siembra schema.sql: así los tests no
        # dependen de qué comercios lleve la lista de arranque, y una regla que
        # cree un test no contamina al siguiente.
        conn.execute(
            """
            INSERT INTO reglas (patron, cat, prioridad) VALUES
              ('mercadona', 'necesidad', 10),
              ('gasolinera', 'necesidad', 10),
              ('netflix', 'deseo', 10)
            """
        )
        conn.execute(
            """
            UPDATE config SET base_mode = 'real', ingreso_base = NULL,
                   pct_necesidades = 50, pct_deseos = 30, pct_ahorro = 20,
                   umbral_amarillo = 0.90
            WHERE id = 1
            """
        )
        conn.execute(
            """
            INSERT INTO usuario (id, password_hash) VALUES (1, %s)
            ON CONFLICT (id) DO UPDATE SET password_hash = EXCLUDED.password_hash
            """,
            (hash_password(PASSWORD),),
        )

    c = TestClient(app)
    c.post("/api/login", json={"password": PASSWORD})
    yield c


def botes(resumen):
    return {b["cat"]: b for b in resumen["botes"]}


# -- Sesión ------------------------------------------------------------------

def test_sin_sesion_no_se_ve_nada():
    anonimo = TestClient(app)
    assert anonimo.get("/api/resumen").status_code == 401


def test_login_y_logout(cliente):
    assert cliente.get("/api/me").json()["autenticado"] is True
    cliente.post("/api/logout")
    assert cliente.get("/api/resumen").status_code == 401


def test_contrasena_incorrecta(cliente):
    c = TestClient(app)
    assert c.post("/api/login", json={"password": "no-es"}).status_code == 401


# -- El recorrido de uso -----------------------------------------------------

def test_el_ingreso_reparte_los_tres_botes(cliente):
    cliente.post("/api/ingresos",
                 json={"concepto": "Nómina", "importe": "2000.00", "tipo": "nomina"})
    b = botes(cliente.get("/api/resumen").json())
    assert b["necesidad"]["presupuesto"] == 1000.0
    assert b["deseo"]["presupuesto"] == 600.0
    assert b["ahorro"]["presupuesto"] == 400.0


def test_el_recurrente_reserva_desde_el_dia_1(cliente):
    cliente.post("/api/ingresos", json={"concepto": "Nómina", "importe": "2000.00"})
    cliente.post("/api/recurrentes", json={
        "concepto": "Seguro coche", "importe": "480.00", "periodicidad": "anual",
        "cat": "necesidad", "mes_cargo": 3, "dia_cargo": 10,
    })
    b = botes(cliente.get("/api/resumen").json())
    assert b["necesidad"]["reservas"] == 40.0
    assert b["necesidad"]["gastado"] == 40.0     # sin haber gastado nada aún
    assert b["necesidad"]["variable"] == 0.0


def test_el_gasto_se_clasifica_solo_por_las_reglas(cliente):
    r = cliente.post("/api/gastos",
                     json={"concepto": "COMPRA TARJ. MERCADONA 4512", "importe": "45.20"})
    assert r.status_code == 200
    gasto = r.json()["gasto"]
    assert gasto["cat"] == "necesidad"     # lo dijo la regla, no el usuario
    assert gasto["regla_id"] is not None
    # Y la barra viene ya actualizada en la misma respuesta.
    assert botes(r.json()["resumen"])["necesidad"]["variable"] == 45.2


def test_un_concepto_desconocido_pide_categoria(cliente):
    r = cliente.post("/api/gastos",
                     json={"concepto": "Ferretería del barrio", "importe": "12.00"})
    assert r.status_code == 422
    r = cliente.post("/api/gastos", json={
        "concepto": "Ferretería del barrio", "importe": "12.00", "cat": "necesidad"})
    assert r.status_code == 200


def test_corregir_la_categoria_ensena_una_regla_nueva(cliente):
    """El usuario manda: si dice que Mercadona es un deseo, a partir de ahora lo es."""
    cliente.post("/api/reglas",
                 json={"patron": "Mercadona", "cat": "deseo", "prioridad": 50})
    gasto = cliente.post("/api/gastos",
                         json={"concepto": "MERCADONA centro", "importe": "30.00"}
                         ).json()["gasto"]
    assert gasto["cat"] == "deseo"


def test_el_cargo_del_recurrente_no_mueve_la_barra(cliente):
    """El punto que hace que la app sirva, visto desde fuera."""
    cliente.post("/api/ingresos", json={"concepto": "Nómina", "importe": "2000.00"})
    rec = cliente.post("/api/recurrentes", json={
        "concepto": "Seguro coche", "importe": "480.00", "periodicidad": "anual",
        "cat": "necesidad", "mes_cargo": 3, "dia_cargo": 10,
    }).json()["recurrente"]

    antes = botes(cliente.get("/api/resumen").json())["necesidad"]
    despues = botes(
        cliente.post(f"/api/recurrentes/{rec['id']}/cargar").json()["resumen"])["necesidad"]

    assert despues == antes                       # ni un céntimo de diferencia
    assert despues["gastado"] == 40.0             # solo la reserva
    # ...pero el gasto sí queda registrado en el historial.
    conceptos = [g["concepto"] for g in cliente.get("/api/gastos").json()]
    assert "Seguro coche" in conceptos


def test_el_cargo_no_se_registra_dos_veces(cliente):
    rec = cliente.post("/api/recurrentes", json={
        "concepto": "Netflix", "importe": "12.99", "periodicidad": "mensual",
        "cat": "deseo", "dia_cargo": 1,
    }).json()["recurrente"]
    assert cliente.post(f"/api/recurrentes/{rec['id']}/cargar").status_code == 200
    assert cliente.post(f"/api/recurrentes/{rec['id']}/cargar").status_code == 409


def test_editar_y_borrar_un_gasto(cliente):
    gasto = cliente.post("/api/gastos", json={
        "concepto": "Cena", "importe": "40.00", "cat": "deseo"}).json()["gasto"]

    r = cliente.patch(f"/api/gastos/{gasto['id']}", json={"importe": "25.00"})
    assert botes(r.json()["resumen"])["deseo"]["variable"] == 25.0

    r = cliente.delete(f"/api/gastos/{gasto['id']}")
    assert botes(r.json()["resumen"])["deseo"]["variable"] == 0.0
    assert cliente.delete(f"/api/gastos/{gasto['id']}").status_code == 404


def test_conceptos_para_el_autocompletado(cliente):
    for _ in range(3):
        cliente.post("/api/gastos",
                     json={"concepto": "Mercadona", "importe": "10.00", "cat": "necesidad"})
    cliente.post("/api/gastos",
                 json={"concepto": "Gasolinera", "importe": "60.00", "cat": "necesidad"})
    conceptos = cliente.get("/api/conceptos").json()
    assert conceptos[0] == "Mercadona"      # el más repetido, primero


# -- Configuración -----------------------------------------------------------

def test_los_porcentajes_tienen_que_sumar_100(cliente):
    r = cliente.patch("/api/config", json={"pct_necesidades": 70})
    assert r.status_code == 422
    assert "100" in r.json()["detail"]

    r = cliente.patch("/api/config", json={
        "pct_necesidades": 60, "pct_deseos": 20, "pct_ahorro": 20})
    assert r.status_code == 200


def test_base_fija(cliente):
    cliente.patch("/api/config",
                  json={"base_mode": "fijo", "ingreso_base": "3000.00"})
    resumen = cliente.get("/api/resumen").json()
    assert resumen["base"] == 3000.0
    assert resumen["base_estimada"] is False
    assert botes(resumen)["necesidad"]["presupuesto"] == 1500.0


def test_base_real_sin_ingresos_se_marca_como_estimada(cliente):
    resumen = cliente.get("/api/resumen").json()
    assert resumen["base_estimada"] is True


def test_un_recurrente_no_mensual_necesita_mes_de_cargo(cliente):
    r = cliente.post("/api/recurrentes", json={
        "concepto": "IBI", "importe": "300.00", "periodicidad": "anual",
        "cat": "necesidad",
    })
    assert r.status_code == 422
