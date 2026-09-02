"""Teresorería — API.

Todo cuelga de /api porque Caddy manda ese prefijo aquí y el resto al frontend.
El cálculo de verdad vive en `calc.py`; aquí solo se lee de la base, se le pasa
y se devuelve. Las rutas exigen sesión salvo `/api/health` y el login.
"""

import logging
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

import avisos
import calc
import push
from auth import (
    clear_cookie,
    hay_sesion,
    issue_cookie,
    require_login,
    verify_password,
)
from clasificar import clasificar, normalizar
from db import get_conn, query, query_one

log = logging.getLogger("teresoreria")

ZONA = ZoneInfo("Europe/Madrid")
planificador = BackgroundScheduler(timezone=ZONA)


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    """Arranca el repaso diario de avisos junto con la API.

    Va dentro del propio proceso (por eso uvicorn corre con un solo worker:
    con varios, el aviso saldría repetido). Si algo falla al programarlo, la
    API arranca igual: preferimos quedarnos sin avisos que sin app.
    """
    try:
        reprogramar_avisos()
        planificador.start()
    except Exception:
        log.exception("No se ha podido arrancar el planificador de avisos")
    yield
    if planificador.running:
        planificador.shutdown(wait=False)


app = FastAPI(title="Teresorería", docs_url=None, redoc_url=None,
              lifespan=ciclo_de_vida)

Categoria = Literal["necesidad", "deseo", "ahorro"]
Periodicidad = Literal["mensual", "bimestral", "trimestral", "semestral", "anual"]

protegido = [Depends(require_login)]


# ── Utilidades de fechas ─────────────────────────────────────────────────────

def hoy() -> date:
    """El "hoy" de la app. El contenedor va con TZ=Europe/Madrid, así que el
    corte de mes y la fecha por defecto de un gasto son los de aquí."""
    return date.today()


def primer_dia(d: date) -> date:
    return d.replace(day=1)


def sumar_meses(d: date, n: int) -> date:
    """Primer día del mes que está `n` meses adelante (o atrás, si n < 0)."""
    total = d.year * 12 + (d.month - 1) + n
    return date(total // 12, total % 12 + 1, 1)


def mes_desde_texto(mes: Optional[str]) -> date:
    """'2026-06' -> date(2026, 6, 1). Sin valor, el mes en curso."""
    if not mes:
        return primer_dia(hoy())
    try:
        anio, m = mes.split("-")
        return date(int(anio), int(m), 1)
    except (ValueError, AttributeError):
        raise HTTPException(422, "El mes debe venir como AAAA-MM.")


# ── Modelos de entrada ───────────────────────────────────────────────────────

class LoginIn(BaseModel):
    password: str


class GastoIn(BaseModel):
    concepto: str = Field(min_length=1, max_length=200)
    importe: Decimal
    cat: Optional[Categoria] = None
    fecha: Optional[date] = None
    nota: Optional[str] = None

    @field_validator("importe")
    @classmethod
    def importe_razonable(cls, v: Decimal) -> Decimal:
        if abs(v) > Decimal("1000000"):
            raise ValueError("Importe fuera de rango.")
        return v


class GastoPatch(BaseModel):
    concepto: Optional[str] = Field(default=None, min_length=1, max_length=200)
    importe: Optional[Decimal] = None
    cat: Optional[Categoria] = None
    fecha: Optional[date] = None
    nota: Optional[str] = None


class IngresoIn(BaseModel):
    concepto: str = Field(min_length=1, max_length=200)
    importe: Decimal
    fecha: Optional[date] = None
    tipo: Literal["nomina", "factura", "otro"] = "otro"


class IngresoPatch(BaseModel):
    concepto: Optional[str] = Field(default=None, min_length=1, max_length=200)
    importe: Optional[Decimal] = None
    fecha: Optional[date] = None
    tipo: Optional[Literal["nomina", "factura", "otro"]] = None


class RecurrenteIn(BaseModel):
    concepto: str = Field(min_length=1, max_length=200)
    importe: Decimal
    periodicidad: Periodicidad
    cat: Categoria
    mes_cargo: Optional[int] = Field(default=None, ge=1, le=12)
    dia_cargo: Optional[int] = Field(default=None, ge=1, le=28)
    activo: bool = True


class RecurrentePatch(BaseModel):
    concepto: Optional[str] = Field(default=None, min_length=1, max_length=200)
    importe: Optional[Decimal] = None
    periodicidad: Optional[Periodicidad] = None
    cat: Optional[Categoria] = None
    mes_cargo: Optional[int] = Field(default=None, ge=1, le=12)
    dia_cargo: Optional[int] = Field(default=None, ge=1, le=28)
    activo: Optional[bool] = None


class ReglaIn(BaseModel):
    patron: str = Field(min_length=2, max_length=100)
    cat: Categoria
    prioridad: int = 0


class ConfigPatch(BaseModel):
    base_mode: Optional[Literal["fijo", "real"]] = None
    ingreso_base: Optional[Decimal] = None
    pct_necesidades: Optional[int] = Field(default=None, ge=0, le=100)
    pct_deseos: Optional[int] = Field(default=None, ge=0, le=100)
    pct_ahorro: Optional[int] = Field(default=None, ge=0, le=100)
    umbral_amarillo: Optional[Decimal] = Field(default=None, ge=0, le=1)
    hora_aviso: Optional[str] = None


# ── Lectura de la configuración ──────────────────────────────────────────────

def leer_config() -> dict:
    cfg = query_one("SELECT * FROM config WHERE id = 1")
    if not cfg:
        raise HTTPException(500, "Falta la fila de configuración.")
    return cfg


def leer_reglas() -> list[dict]:
    return query("SELECT * FROM reglas")


# ── Salud y sesión ───────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    """Si hay sesión y si el usuario está creado (para avisar en el login)."""
    usuario = query_one("SELECT 1 AS existe FROM usuario WHERE id = 1")
    return {"autenticado": hay_sesion(request), "configurado": bool(usuario)}


@app.post("/api/login")
def login(datos: LoginIn, response: Response):
    usuario = query_one("SELECT password_hash FROM usuario WHERE id = 1")
    if not usuario:
        raise HTTPException(
            409, "Todavía no hay contraseña. Créala con: python manage.py set-password"
        )
    if not verify_password(usuario["password_hash"], datos.password):
        raise HTTPException(401, "Contraseña incorrecta.")
    issue_cookie(response)
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response):
    clear_cookie(response)
    return {"ok": True}


# ── Resumen: la llamada central ──────────────────────────────────────────────

def construir_resumen() -> dict:
    d = hoy()
    desde = primer_dia(d)
    hasta = sumar_meses(desde, 1)
    tres_meses_atras = sumar_meses(desde, -3)

    cfg = leer_config()
    ingresos_mes = query(
        "SELECT * FROM ingresos WHERE fecha >= %s AND fecha < %s", (desde, hasta))
    ingresos_previos = query(
        "SELECT * FROM ingresos WHERE fecha >= %s AND fecha < %s", (tres_meses_atras, desde))
    recurrentes = query("SELECT * FROM recurrentes WHERE activo")
    gastos_mes = query(
        "SELECT * FROM gastos WHERE fecha >= %s AND fecha < %s", (desde, hasta))

    resumen = calc.calcular_resumen(
        cfg, ingresos_mes, ingresos_previos, recurrentes, gastos_mes, d)
    resumen["ingresos_mes"] = calc.dos(
        sum((i["importe"] for i in ingresos_mes), Decimal(0)))
    resumen["ultimos_gastos"] = query(
        "SELECT * FROM gastos ORDER BY fecha DESC, id DESC LIMIT 5")
    return resumen


@app.get("/api/resumen", dependencies=protegido)
def get_resumen():
    return construir_resumen()


# ── Gastos ───────────────────────────────────────────────────────────────────

@app.get("/api/gastos", dependencies=protegido)
def listar_gastos(mes: Optional[str] = None, cat: Optional[Categoria] = None):
    desde = mes_desde_texto(mes)
    hasta = sumar_meses(desde, 1)
    sql = "SELECT * FROM gastos WHERE fecha >= %s AND fecha < %s"
    params: tuple = (desde, hasta)
    if cat:
        sql += " AND cat = %s"
        params += (cat,)
    return query(sql + " ORDER BY fecha DESC, id DESC", params)


@app.post("/api/gastos", dependencies=protegido)
def crear_gasto(datos: GastoIn):
    """Guarda el gasto y devuelve el resumen ya recalculado.

    Devolver el resumen en la misma respuesta ahorra una ida y vuelta: la barra
    del resumen se actualiza en cuanto se guarda, sin recargar nada.
    """
    cat, regla_id = datos.cat, None
    if cat is None:
        cat, regla_id = clasificar(datos.concepto, leer_reglas())
    if cat is None:
        raise HTTPException(422, "Elige una categoría: ninguna regla reconoce ese concepto.")

    with get_conn() as conn:
        gasto = conn.execute(
            """
            INSERT INTO gastos (fecha, concepto, importe, cat, regla_id, nota)
            VALUES (COALESCE(%s, CURRENT_DATE), %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (datos.fecha, datos.concepto.strip(), datos.importe, cat, regla_id, datos.nota),
        ).fetchone()
        # La regla que acierta sube en el orden: se usará antes la próxima vez.
        if regla_id:
            conn.execute("UPDATE reglas SET usos = usos + 1 WHERE id = %s", (regla_id,))

    return {"gasto": gasto, "resumen": construir_resumen()}


@app.patch("/api/gastos/{gasto_id}", dependencies=protegido)
def editar_gasto(gasto_id: int, datos: GastoPatch):
    campos = datos.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(400, "Nada que cambiar.")
    # Las claves salen del modelo de pydantic, no del cuerpo crudo: no hay
    # forma de colar un nombre de columna arbitrario aquí.
    sets = ", ".join(f"{k} = %s" for k in campos)

    with get_conn() as conn:
        gasto = conn.execute(
            f"UPDATE gastos SET {sets} WHERE id = %s RETURNING *",
            (*campos.values(), gasto_id),
        ).fetchone()
    if not gasto:
        raise HTTPException(404, "Ese gasto no existe.")
    return {"gasto": gasto, "resumen": construir_resumen()}


@app.delete("/api/gastos/{gasto_id}", dependencies=protegido)
def borrar_gasto(gasto_id: int):
    with get_conn() as conn:
        borrado = conn.execute(
            "DELETE FROM gastos WHERE id = %s RETURNING id", (gasto_id,)).fetchone()
    if not borrado:
        raise HTTPException(404, "Ese gasto no existe.")
    return {"ok": True, "resumen": construir_resumen()}


@app.get("/api/conceptos", dependencies=protegido)
def conceptos():
    """Conceptos ya usados, los más frecuentes primero (autocompletado)."""
    filas = query(
        """
        SELECT concepto, COUNT(*) AS veces
        FROM gastos
        GROUP BY concepto
        ORDER BY veces DESC, MAX(fecha) DESC
        LIMIT 100
        """
    )
    return [f["concepto"] for f in filas]


# ── Ingresos ─────────────────────────────────────────────────────────────────

@app.get("/api/ingresos", dependencies=protegido)
def listar_ingresos(mes: Optional[str] = None):
    if mes:
        desde = mes_desde_texto(mes)
        return query(
            "SELECT * FROM ingresos WHERE fecha >= %s AND fecha < %s ORDER BY fecha DESC, id DESC",
            (desde, sumar_meses(desde, 1)),
        )
    return query("SELECT * FROM ingresos ORDER BY fecha DESC, id DESC LIMIT 100")


@app.post("/api/ingresos", dependencies=protegido)
def crear_ingreso(datos: IngresoIn):
    with get_conn() as conn:
        ingreso = conn.execute(
            """
            INSERT INTO ingresos (fecha, concepto, importe, tipo)
            VALUES (COALESCE(%s, CURRENT_DATE), %s, %s, %s)
            RETURNING *
            """,
            (datos.fecha, datos.concepto.strip(), datos.importe, datos.tipo),
        ).fetchone()
    return {"ingreso": ingreso, "resumen": construir_resumen()}


@app.patch("/api/ingresos/{ingreso_id}", dependencies=protegido)
def editar_ingreso(ingreso_id: int, datos: IngresoPatch):
    campos = datos.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(400, "Nada que cambiar.")
    sets = ", ".join(f"{k} = %s" for k in campos)
    with get_conn() as conn:
        ingreso = conn.execute(
            f"UPDATE ingresos SET {sets} WHERE id = %s RETURNING *",
            (*campos.values(), ingreso_id),
        ).fetchone()
    if not ingreso:
        raise HTTPException(404, "Ese ingreso no existe.")
    return {"ingreso": ingreso, "resumen": construir_resumen()}


@app.delete("/api/ingresos/{ingreso_id}", dependencies=protegido)
def borrar_ingreso(ingreso_id: int):
    with get_conn() as conn:
        borrado = conn.execute(
            "DELETE FROM ingresos WHERE id = %s RETURNING id", (ingreso_id,)).fetchone()
    if not borrado:
        raise HTTPException(404, "Ese ingreso no existe.")
    return {"ok": True, "resumen": construir_resumen()}


# ── Recurrentes ──────────────────────────────────────────────────────────────

def _adornar_recurrente(r: dict, d: date, cargados: set[int]) -> dict:
    """Añade lo que la interfaz necesita y que no está en la tabla."""
    return {
        **r,
        "reserva_mensual": calc.reserva_mensual(r),
        # Con estos dos la pantalla decide si enseña el botón de "ya se ha
        # cargado": toca este mes, y todavía no está registrado.
        "toca_cargar": calc.toca_cargar(r, d),
        "cargado_este_mes": r["id"] in cargados,
    }


@app.get("/api/recurrentes", dependencies=protegido)
def listar_recurrentes():
    d = hoy()
    desde = primer_dia(d)
    filas = query("SELECT * FROM recurrentes ORDER BY cat, concepto")
    cargados = {
        g["recurrente_id"]
        for g in query(
            """
            SELECT DISTINCT recurrente_id FROM gastos
            WHERE recurrente_id IS NOT NULL AND fecha >= %s AND fecha < %s
            """,
            (desde, sumar_meses(desde, 1)),
        )
    }
    return [_adornar_recurrente(r, d, cargados) for r in filas]


@app.post("/api/recurrentes", dependencies=protegido)
def crear_recurrente(datos: RecurrenteIn):
    if datos.periodicidad != "mensual" and datos.mes_cargo is None:
        raise HTTPException(422, "Un recurrente no mensual necesita saber en qué mes carga.")
    with get_conn() as conn:
        rec = conn.execute(
            """
            INSERT INTO recurrentes (concepto, importe, periodicidad, mes_cargo,
                                     dia_cargo, cat, activo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (datos.concepto.strip(), datos.importe, datos.periodicidad,
             datos.mes_cargo, datos.dia_cargo, datos.cat, datos.activo),
        ).fetchone()
    return {"recurrente": _adornar_recurrente(rec, hoy(), set()),
            "resumen": construir_resumen()}


@app.patch("/api/recurrentes/{rec_id}", dependencies=protegido)
def editar_recurrente(rec_id: int, datos: RecurrentePatch):
    campos = datos.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(400, "Nada que cambiar.")
    sets = ", ".join(f"{k} = %s" for k in campos)
    with get_conn() as conn:
        rec = conn.execute(
            f"UPDATE recurrentes SET {sets} WHERE id = %s RETURNING *",
            (*campos.values(), rec_id),
        ).fetchone()
    if not rec:
        raise HTTPException(404, "Ese recurrente no existe.")
    return {"recurrente": _adornar_recurrente(rec, hoy(), set()),
            "resumen": construir_resumen()}


@app.delete("/api/recurrentes/{rec_id}", dependencies=protegido)
def borrar_recurrente(rec_id: int):
    """Los gastos que ya cargó se quedan (con `recurrente_id` a NULL por la FK):
    borrar el recurrente no debe borrar el historial de lo que se pagó."""
    with get_conn() as conn:
        borrado = conn.execute(
            "DELETE FROM recurrentes WHERE id = %s RETURNING id", (rec_id,)).fetchone()
    if not borrado:
        raise HTTPException(404, "Ese recurrente no existe.")
    return {"ok": True, "resumen": construir_resumen()}


@app.post("/api/recurrentes/{rec_id}/cargar", dependencies=protegido)
def cargar_recurrente(rec_id: int):
    """Registra el cargo real de un recurrente como gasto.

    El gasto queda atado a su `recurrente_id`, y por eso NO mueve la barra: ese
    dinero llevaba reservado desde el día 1. En F2 esto se pulsa a mano; cuando
    haya planificador (F3) podrá dispararlo él llamando aquí mismo.
    """
    d = hoy()
    desde = primer_dia(d)
    with get_conn() as conn:
        rec = conn.execute(
            "SELECT * FROM recurrentes WHERE id = %s", (rec_id,)).fetchone()
        if not rec:
            raise HTTPException(404, "Ese recurrente no existe.")

        ya = conn.execute(
            """
            SELECT id FROM gastos
            WHERE recurrente_id = %s AND fecha >= %s AND fecha < %s
            """,
            (rec_id, desde, sumar_meses(desde, 1)),
        ).fetchone()
        if ya:
            raise HTTPException(409, "Ese cargo ya está registrado este mes.")

        gasto = conn.execute(
            """
            INSERT INTO gastos (fecha, concepto, importe, cat, recurrente_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (d, rec["concepto"], rec["importe"], rec["cat"], rec_id),
        ).fetchone()

    return {"gasto": gasto, "resumen": construir_resumen()}


# ── Reglas ───────────────────────────────────────────────────────────────────

@app.get("/api/reglas", dependencies=protegido)
def listar_reglas():
    """El frontend se las lleva enteras para preseleccionar la categoría
    mientras se escribe, sin ir al servidor en cada tecla."""
    return query("SELECT * FROM reglas ORDER BY prioridad DESC, usos DESC, patron")


@app.post("/api/reglas", dependencies=protegido)
def guardar_regla(datos: ReglaIn):
    """Crea la regla o, si ya existe ese patrón, le cambia la categoría.

    Es lo que pasa cuando se corrige la categoría de un gasto y se acepta que a
    partir de ahora ese concepto vaya al bote nuevo.
    """
    patron = normalizar(datos.patron)
    if not patron:
        raise HTTPException(422, "El patrón no puede quedar vacío.")

    with get_conn() as conn:
        existente = conn.execute(
            "SELECT id FROM reglas WHERE patron = %s", (patron,)).fetchone()
        if existente:
            regla = conn.execute(
                "UPDATE reglas SET cat = %s, prioridad = %s WHERE id = %s RETURNING *",
                (datos.cat, datos.prioridad, existente["id"]),
            ).fetchone()
        else:
            regla = conn.execute(
                "INSERT INTO reglas (patron, cat, prioridad) VALUES (%s, %s, %s) RETURNING *",
                (patron, datos.cat, datos.prioridad),
            ).fetchone()
    return regla


@app.delete("/api/reglas/{regla_id}", dependencies=protegido)
def borrar_regla(regla_id: int):
    with get_conn() as conn:
        borrado = conn.execute(
            "DELETE FROM reglas WHERE id = %s RETURNING id", (regla_id,)).fetchone()
    if not borrado:
        raise HTTPException(404, "Esa regla no existe.")
    return {"ok": True}


# ── Configuración ────────────────────────────────────────────────────────────

@app.get("/api/config", dependencies=protegido)
def get_config():
    return leer_config()


@app.patch("/api/config", dependencies=protegido)
def editar_config(datos: ConfigPatch):
    campos = datos.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(400, "Nada que cambiar.")

    # Los porcentajes tienen que seguir sumando 100 después del cambio, así que
    # se comprueban contra lo que ya hay, no solo contra lo que llega.
    actual = leer_config()
    pcts = {k: campos.get(k, actual[k])
            for k in ("pct_necesidades", "pct_deseos", "pct_ahorro")}
    if sum(pcts.values()) != 100:
        raise HTTPException(
            422, f"Los porcentajes tienen que sumar 100 (suman {sum(pcts.values())}).")

    if campos.get("base_mode") == "fijo" and not (
            campos.get("ingreso_base") or actual["ingreso_base"]):
        raise HTTPException(422, "Con base fija hay que declarar el ingreso base.")

    sets = ", ".join(f"{k} = %s" for k in campos)
    with get_conn() as conn:
        cfg = conn.execute(
            f"UPDATE config SET {sets} WHERE id = 1 RETURNING *",
            tuple(campos.values()),
        ).fetchone()

    # La hora del aviso solo se lee al programar el trabajo, así que si cambia
    # hay que reprogramarlo o seguiría saltando a la hora vieja hasta el
    # siguiente reinicio.
    if "hora_aviso" in campos and planificador.running:
        try:
            reprogramar_avisos()
        except Exception:
            log.exception("No se ha podido reprogramar el aviso diario")

    return {"config": cfg, "resumen": construir_resumen()}


# ── Notificaciones push ──────────────────────────────────────────────────────

class ClavesPush(BaseModel):
    p256dh: str
    auth: str


class SuscripcionIn(BaseModel):
    endpoint: str
    keys: ClavesPush


class BajaIn(BaseModel):
    endpoint: str


def _suscripciones() -> list[dict]:
    """Las suscripciones en el formato que espera pywebpush."""
    return [
        {"endpoint": f["endpoint"],
         "keys": {"p256dh": f["p256dh"], "auth": f["auth"]}}
        for f in query("SELECT endpoint, p256dh, auth FROM push_subscriptions")
    ]


def enviar_a_todos(titulo: str, cuerpo: str) -> int:
    """Manda el aviso a todos los dispositivos. Devuelve cuántos lo recibieron.

    Las suscripciones que el navegador ya ha tirado (desinstalar la app, borrar
    los datos del sitio) se borran solas: si no, la tabla se llena de endpoints
    muertos y cada aviso tarda diez segundos en dar error por cada uno.
    """
    if not push.configurado():
        return 0

    entregados, caducadas = 0, []
    for suscripcion in _suscripciones():
        enviado, codigo = push.enviar(suscripcion, titulo, cuerpo)
        if enviado:
            entregados += 1
        elif codigo in push.CADUCADA:
            caducadas.append(suscripcion["endpoint"])
        else:
            log.warning("Push fallido (%s) en %s", codigo, suscripcion["endpoint"][:40])

    if caducadas:
        with get_conn() as conn:
            conn.execute(
                "DELETE FROM push_subscriptions WHERE endpoint = ANY(%s)", (caducadas,))
    return entregados


def revisar_avisos() -> dict:
    """El repaso diario: mira los tres botes y manda lo que toque."""
    mes = primer_dia(hoy())
    resumen = construir_resumen()

    ya_enviados = {
        (f["cat"], f["nivel"])
        for f in query("SELECT cat, nivel FROM avisos_enviados WHERE mes = %s", (mes,))
    }
    plan = avisos.decidir(resumen, ya_enviados)

    with get_conn() as conn:
        # Los botes que han vuelto a verde pierden sus filas: si se tuercen
        # otra vez este mes, el aviso tiene que volver a saltar.
        for cat in plan["rearmar"]:
            conn.execute(
                "DELETE FROM avisos_enviados WHERE mes = %s AND cat = %s", (mes, cat))

    entregados = 0
    for aviso in plan["enviar"]:
        n = enviar_a_todos(aviso["titulo"], aviso["cuerpo"])
        entregados += n
        # Solo se da por avisado si de verdad llegó a algún sitio. Si todavía
        # no hay ningún móvil suscrito, mañana se vuelve a intentar en vez de
        # perder el aviso de este mes.
        if n:
            with get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO avisos_enviados (mes, cat, nivel) VALUES (%s, %s, %s)
                    ON CONFLICT (mes, cat, nivel) DO NOTHING
                    """,
                    (mes, aviso["cat"], aviso["nivel"]),
                )

    log.info("Repaso de avisos: %d por mandar, %d entregados, %d rearmados",
             len(plan["enviar"]), entregados, len(plan["rearmar"]))
    return {"revisados": len(resumen["botes"]), "avisos": plan["enviar"],
            "entregados": entregados, "rearmados": plan["rearmar"]}


def reprogramar_avisos() -> None:
    """(Re)programa el repaso diario a la hora que diga la configuración."""
    hora = leer_config()["hora_aviso"]
    planificador.add_job(
        revisar_avisos,
        CronTrigger(hour=hora.hour, minute=hora.minute, timezone=ZONA),
        id="avisos",
        replace_existing=True,
        # Si el contenedor estaba reiniciándose justo a esa hora, todavía vale.
        misfire_grace_time=3600,
    )


@app.get("/api/push/clave", dependencies=protegido)
def clave_push():
    return {"clave": push.clave_publica(), "configurado": push.configurado()}


@app.get("/api/push/estado", dependencies=protegido)
def estado_push():
    total = query_one("SELECT count(*) AS n FROM push_subscriptions")
    proximo = planificador.get_job("avisos") if planificador.running else None
    return {
        "configurado": push.configurado(),
        "dispositivos": total["n"] if total else 0,
        "proximo_repaso": proximo.next_run_time.isoformat() if proximo else None,
    }


@app.post("/api/push/suscribir", dependencies=protegido)
def suscribir(datos: SuscripcionIn, request: Request):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO push_subscriptions (endpoint, p256dh, auth, user_agent)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (endpoint) DO UPDATE
              SET p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth
            """,
            (datos.endpoint, datos.keys.p256dh, datos.keys.auth,
             request.headers.get("user-agent")),
        )
    return {"ok": True}


@app.post("/api/push/baja", dependencies=protegido)
def dar_de_baja(datos: BajaIn):
    with get_conn() as conn:
        conn.execute("DELETE FROM push_subscriptions WHERE endpoint = %s",
                     (datos.endpoint,))
    return {"ok": True}


@app.post("/api/push/prueba", dependencies=protegido)
def probar_push():
    """Un aviso de prueba, para comprobar que llega antes de fiarse."""
    if not push.configurado():
        raise HTTPException(409, "Faltan las claves VAPID en el servidor.")
    entregados = enviar_a_todos(
        "Teresorería", "Los avisos funcionan. Te avisaré antes de que te pases.")
    if not entregados:
        raise HTTPException(409, "No hay ningún dispositivo suscrito (o ya caducó).")
    return {"entregados": entregados}


@app.post("/api/avisos/revisar", dependencies=protegido)
def revisar_ahora():
    """Lanza el repaso a mano, sin esperar a la hora del aviso."""
    return revisar_avisos()
