"""Reparto en botes, prorrateo de recurrentes y proyección a fin de mes.

Módulo **puro**: no sabe de FastAPI ni de SQL. Recibe listas de diccionarios
(tal cual salen de psycopg con `dict_row`) y devuelve números. Así se puede
probar a fondo, que falta hace: es donde un error hace que la app mienta.

Todo el dinero va en `Decimal`. Nunca `float`.
"""

import calendar
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Optional

CATEGORIAS = ("necesidad", "deseo", "ahorro")

# Meses que cubre cada cargo. Es la tabla que hace posible el prorrateo.
MESES_PERIODO = {
    "mensual": 1,
    "bimestral": 2,
    "trimestral": 3,
    "semestral": 6,
    "anual": 12,
}

# Con tres días de datos la proyección es ruido puro: hasta pasado el día 5 se
# pinta el estado en pantalla pero no se notifica.
DIAS_SIN_AVISO = 5

CENT = Decimal("0.01")


def _dec(valor: Any) -> Decimal:
    """Convierte a Decimal sin pasar por float (que introduciría basura)."""
    if isinstance(valor, Decimal):
        return valor
    if valor is None:
        return Decimal(0)
    return Decimal(str(valor))


def dos(valor: Any) -> Decimal:
    """Redondea a céntimos, al alza en el empate (como se redondea el dinero)."""
    return _dec(valor).quantize(CENT, rounding=ROUND_HALF_UP)


# ── Prorrateo ────────────────────────────────────────────────────────────────

def reserva_mensual(recurrente: dict) -> Decimal:
    """Lo que hay que apartar cada mes para llegar al cargo completo.

    El seguro de coche de 480 € anuales no se imputa entero al mes del cargo:
    son 40 € cada mes. Es el cálculo que evita que los meses con cargos anuales
    salgan todos en rojo.
    """
    meses = MESES_PERIODO[recurrente["periodicidad"]]
    return dos(_dec(recurrente["importe"]) / meses)


def reservas_de(recurrentes: Iterable[dict], cat: str) -> Decimal:
    """Suma de las reservas mensuales de los recurrentes activos de un bote."""
    return dos(
        sum(
            (reserva_mensual(r) for r in recurrentes if r["cat"] == cat and r.get("activo", True)),
            Decimal(0),
        )
    )


# ── Base de cálculo ──────────────────────────────────────────────────────────

def base_del_mes(
    config: dict,
    ingresos_mes: Iterable[dict],
    ingresos_previos: Iterable[dict] = (),
) -> tuple[Decimal, bool]:
    """Devuelve `(base, estimada)`.

    - Modo `fijo`: el ingreso base declarado en Ajustes.
    - Modo `real`: lo ingresado este mes. Mientras no haya nada registrado se
      usa la media de los meses previos como estimación provisional, y se marca
      con `estimada=True` para que la interfaz lo diga en vez de fingir certeza.

    La media divide entre los meses que *tuvieron* ingresos, no entre 3 fijo:
    en el primer mes de uso dividir entre 3 daría una base ridícula.
    """
    if config.get("base_mode") == "fijo":
        return dos(config.get("ingreso_base") or 0), False

    total_mes = sum((_dec(i["importe"]) for i in ingresos_mes), Decimal(0))
    if total_mes > 0:
        return dos(total_mes), False

    previos = list(ingresos_previos)
    if not previos:
        return Decimal("0.00"), True

    meses_con_datos = len({(i["fecha"].year, i["fecha"].month) for i in previos})
    total_previo = sum((_dec(i["importe"]) for i in previos), Decimal(0))
    return dos(total_previo / max(1, meses_con_datos)), True


# ── Botes, proyección y estado ───────────────────────────────────────────────

def _pct(config: dict, cat: str) -> int:
    return int(config[{"necesidad": "pct_necesidades",
                       "deseo": "pct_deseos",
                       "ahorro": "pct_ahorro"}[cat]])


def estado_de(presupuesto: Decimal, gastado: Decimal, proyeccion: Decimal,
              umbral: Decimal) -> str:
    """Rojo / amarillo / verde según lo previsto a fin de mes.

    Hay dos maneras de estar en rojo: que la proyección se pase, o que ya te
    hayas pasado de hecho (lo segundo no es una previsión, es un hecho).
    """
    if proyeccion > presupuesto or gastado > presupuesto:
        return "rojo"
    if proyeccion > presupuesto * umbral:
        return "amarillo"
    return "verde"


def calcular_bote(
    cat: str,
    base: Decimal,
    config: dict,
    recurrentes: Iterable[dict],
    gastos_mes: Iterable[dict],
    dia: int,
    dias_mes: int,
) -> dict:
    """Estado completo de un bote en el día `dia` de un mes de `dias_mes` días."""
    pct = _pct(config, cat)
    presupuesto = dos(base * pct / 100)
    reservas = reservas_de(recurrentes, cat)

    # Solo el gasto VARIABLE marca el ritmo. Un gasto con `recurrente_id` es el
    # cargo de algo ya reservado desde el día 1: contarlo sería contarlo dos
    # veces, y el mes del recibo anual saldría en rojo sin motivo.
    variable = dos(
        sum(
            (_dec(g["importe"]) for g in gastos_mes
             if g["cat"] == cat and g.get("recurrente_id") is None),
            Decimal(0),
        )
    )

    gastado = dos(reservas + variable)
    ritmo_diario = _dec(variable) / dia
    proyeccion = dos(reservas + ritmo_diario * dias_mes)
    umbral = _dec(config.get("umbral_amarillo", "0.90"))

    return {
        "cat": cat,
        "pct": pct,
        "presupuesto": presupuesto,
        "reservas": reservas,
        "variable": variable,
        "gastado": gastado,
        "restante": dos(presupuesto - gastado),
        "ritmo_diario": dos(ritmo_diario),
        "proyeccion": proyeccion,
        "estado": estado_de(presupuesto, gastado, proyeccion, umbral),
        # F3 leerá esto para decidir si además de pintar, notifica.
        "avisable": dia > DIAS_SIN_AVISO,
    }


def calcular_resumen(
    config: dict,
    ingresos_mes: Iterable[dict],
    ingresos_previos: Iterable[dict],
    recurrentes: Iterable[dict],
    gastos_mes: Iterable[dict],
    hoy,
) -> dict:
    """El cálculo completo del mes en curso: base + los tres botes."""
    recurrentes = list(recurrentes)
    gastos_mes = list(gastos_mes)

    base, estimada = base_del_mes(config, ingresos_mes, ingresos_previos)
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]

    return {
        "mes": hoy.strftime("%Y-%m"),
        "dia": hoy.day,
        "dias_mes": dias_mes,
        "dias_restantes": dias_mes - hoy.day,
        "base": base,
        "base_estimada": estimada,
        "base_mode": config.get("base_mode", "real"),
        "botes": [
            calcular_bote(cat, base, config, recurrentes, gastos_mes,
                          hoy.day, dias_mes)
            for cat in CATEGORIAS
        ],
    }


# ── Recurrentes: ¿toca cargar? ───────────────────────────────────────────────

def toca_cargar(recurrente: dict, hoy) -> bool:
    """Si a este recurrente le corresponde cargo en el mes en curso y ya pasó
    su día. La pantalla de recurrentes usa esto para ofrecer el botón de
    registrar el cargo con un toque (en F2 no hay cron que lo haga solo).
    """
    if not recurrente.get("activo", True):
        return False

    meses = MESES_PERIODO[recurrente["periodicidad"]]
    if meses > 1:
        mes_cargo = recurrente.get("mes_cargo")
        if mes_cargo is None:
            return False
        # Un trimestral que carga en marzo carga también en junio, septiembre
        # y diciembre: el mes del cargo se repite cada `meses`.
        if (hoy.month - int(mes_cargo)) % meses != 0:
            return False

    dia_cargo = recurrente.get("dia_cargo")
    return hoy.day >= int(dia_cargo) if dia_cargo else True
