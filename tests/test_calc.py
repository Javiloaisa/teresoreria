"""Tests del motor de cálculo.

Aquí está lo que de verdad hay que blindar. Si el prorrateo falla, la app miente
en la única pantalla que se mira, y una app de dinero que miente se abandona.
"""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

import pytest  # noqa: E402

from calc import (  # noqa: E402
    base_del_mes,
    calcular_bote,
    calcular_resumen,
    reserva_mensual,
    toca_cargar,
)

D = Decimal


def config(**cambios):
    base = {
        "base_mode": "fijo",
        "ingreso_base": D("2000.00"),
        "pct_necesidades": 50,
        "pct_deseos": 30,
        "pct_ahorro": 20,
        "umbral_amarillo": D("0.90"),
    }
    base.update(cambios)
    return base


def rec(importe, periodicidad, cat="necesidad", **extra):
    r = {"id": 1, "concepto": "x", "importe": D(importe),
         "periodicidad": periodicidad, "cat": cat, "activo": True,
         "mes_cargo": None, "dia_cargo": None}
    r.update(extra)
    return r


def gasto(importe, cat="necesidad", recurrente_id=None):
    return {"importe": D(importe), "cat": cat, "recurrente_id": recurrente_id}


# -- Prorrateo ---------------------------------------------------------------

@pytest.mark.parametrize("importe,periodicidad,esperado", [
    ("480.00", "anual",      "40.00"),   # el seguro de coche del encargo
    ("90.00",  "trimestral", "30.00"),
    ("120.00", "semestral",  "20.00"),
    ("50.00",  "bimestral",  "25.00"),
    ("60.00",  "mensual",    "60.00"),   # mensual: el cargo entero cada mes
    ("100.00", "anual",       "8.33"),   # redondeo a céntimos
])
def test_reserva_mensual(importe, periodicidad, esperado):
    assert reserva_mensual(rec(importe, periodicidad)) == D(esperado)


def test_la_reserva_se_descuenta_desde_el_dia_1():
    """Sin haber gastado nada, el bote arranca con la reserva ya consumida."""
    bote = calcular_bote("necesidad", D("2000.00"), config(),
                         [rec("480.00", "anual")], [], dia=1, dias_mes=31)
    assert bote["reservas"] == D("40.00")
    assert bote["variable"] == D("0.00")
    assert bote["gastado"] == D("40.00")
    assert bote["estado"] == "verde"


def test_el_cargo_real_no_mueve_la_barra():
    """EL test que decide si la app sirve.

    Cuando llega el recibo de 480 EUR del seguro, se registra como gasto con su
    recurrente_id. Ese mes tiene que quedar EXACTAMENTE igual que cualquier
    otro: el dinero ya estaba apartado. Si esto falla, todos los meses con
    cargos anuales salen en rojo, se dejan de mirar los avisos y la app muere.
    """
    recurrentes = [rec("480.00", "anual")]
    comun = dict(base=D("2000.00"), config=config(), recurrentes=recurrentes,
                 dia=15, dias_mes=30)

    mes_normal = calcular_bote("necesidad", gastos_mes=[], **comun)
    mes_del_cargo = calcular_bote(
        "necesidad", gastos_mes=[gasto("480.00", recurrente_id=1)], **comun)

    assert mes_del_cargo == mes_normal
    assert mes_del_cargo["variable"] == D("0.00")
    assert mes_del_cargo["ritmo_diario"] == D("0.00")
    assert mes_del_cargo["estado"] == "verde"


def test_el_gasto_variable_del_mismo_bote_si_cuenta():
    """El contrapunto: sin recurrente_id es gasto variable y sí marca ritmo."""
    bote = calcular_bote("necesidad", D("2000.00"), config(),
                         [rec("480.00", "anual")],
                         [gasto("300.00"), gasto("480.00", recurrente_id=1)],
                         dia=15, dias_mes=30)
    assert bote["variable"] == D("300.00")
    assert bote["gastado"] == D("340.00")          # 40 de reserva + 300 variable
    assert bote["ritmo_diario"] == D("20.00")      # 300 / 15 dias
    assert bote["proyeccion"] == D("640.00")       # 40 + 20 x 30


def test_solo_cuentan_los_recurrentes_activos():
    activo = rec("480.00", "anual")
    apagado = rec("120.00", "anual", id=2, activo=False)
    bote = calcular_bote("necesidad", D("2000.00"), config(), [activo, apagado],
                         [], dia=10, dias_mes=30)
    assert bote["reservas"] == D("40.00")


def test_cada_recurrente_va_a_su_bote():
    recurrentes = [rec("480.00", "anual", "necesidad"),
                   rec("120.00", "anual", "deseo", id=2)]
    resumen = calcular_resumen(config(), [], [], recurrentes, [], date(2026, 6, 15))
    por_cat = {b["cat"]: b for b in resumen["botes"]}
    assert por_cat["necesidad"]["reservas"] == D("40.00")
    assert por_cat["deseo"]["reservas"] == D("10.00")
    assert por_cat["ahorro"]["reservas"] == D("0.00")


# -- Estados -----------------------------------------------------------------
# Presupuesto de necesidades = 2000 x 50% = 1000. Umbral amarillo = 900.

@pytest.mark.parametrize("variable,estado,proyeccion", [
    ("300.00", "verde",    "900.00"),   # justo en el umbral: todavia verde
    ("310.00", "amarillo", "930.00"),   # entre el umbral y el presupuesto
    ("333.33", "amarillo", "999.99"),   # un centimo por debajo del tope
    ("350.00", "rojo",    "1050.00"),   # la proyeccion se pasa
])
def test_estados_en_las_fronteras(variable, estado, proyeccion):
    bote = calcular_bote("necesidad", D("2000.00"), config(), [],
                         [gasto(variable)], dia=10, dias_mes=30)
    assert bote["proyeccion"] == D(proyeccion)
    assert bote["estado"] == estado


def test_rojo_por_hecho_consumado():
    """El segundo camino al rojo: ya te has pasado, no es una prevision.

    Con gastos positivos la proyeccion nunca es menor que lo gastado, asi que
    esta condicion solo se dispara sola cuando entra una devolucion (importe
    negativo) que baja el ritmo pero no deshace lo ya comprometido.
    """
    bote = calcular_bote(
        "necesidad", D("2000.00"), config(),
        [rec("13200.00", "anual")],            # 1100 EUR/mes de reserva
        [gasto("-50.00")],                     # una devolucion
        dia=15, dias_mes=30)
    assert bote["gastado"] == D("1050.00")     # por encima del presupuesto de 1000
    assert bote["proyeccion"] == D("1000.00")  # la proyeccion aun no se pasa
    assert bote["estado"] == "rojo"


def test_umbral_configurable():
    apretado = config(umbral_amarillo=D("0.70"))
    bote = calcular_bote("necesidad", D("2000.00"), apretado, [],
                         [gasto("250.00")], dia=10, dias_mes=30)
    assert bote["proyeccion"] == D("750.00")   # 75 % del presupuesto
    assert bote["estado"] == "amarillo"        # con 0.90 habria sido verde


def test_porcentajes_configurables():
    resumen = calcular_resumen(config(pct_necesidades=60, pct_deseos=20,
                                      pct_ahorro=20),
                               [], [], [], [], date(2026, 6, 15))
    presupuestos = {b["cat"]: b["presupuesto"] for b in resumen["botes"]}
    assert presupuestos == {"necesidad": D("1200.00"), "deseo": D("400.00"),
                            "ahorro": D("400.00")}


# -- Avisos: los primeros dias no --------------------------------------------

@pytest.mark.parametrize("dia,avisable", [(1, False), (5, False), (6, True), (28, True)])
def test_no_se_avisa_los_primeros_cinco_dias(dia, avisable):
    bote = calcular_bote("necesidad", D("2000.00"), config(), [],
                         [gasto("900.00")], dia=dia, dias_mes=30)
    # El estado se calcula y se pinta todos los dias del mes (el nivel concreto
    # depende del ritmo, que cambia segun cuantos dias lleven pasados)...
    assert bote["estado"] in ("amarillo", "rojo")
    # ...pero hasta pasado el dia 5 no se notifica: con tres dias de datos la
    # proyeccion es ruido puro.
    assert bote["avisable"] is avisable


# -- Base de calculo ---------------------------------------------------------

def ingreso(importe, fecha):
    return {"importe": D(importe), "fecha": fecha}


def test_base_fija():
    assert base_del_mes(config(), [], []) == (D("2000.00"), False)


def test_base_real_con_ingresos_del_mes():
    cfg = config(base_mode="real", ingreso_base=None)
    ingresos = [ingreso("1200.00", date(2026, 6, 1)),
                ingreso("450.50", date(2026, 6, 20))]
    assert base_del_mes(cfg, ingresos, []) == (D("1650.50"), False)


def test_base_real_sin_ingresos_estima_con_la_media():
    cfg = config(base_mode="real", ingreso_base=None)
    previos = [ingreso("1800.00", date(2026, 3, 5)),
               ingreso("2100.00", date(2026, 4, 5)),
               ingreso("2400.00", date(2026, 5, 5))]
    base, estimada = base_del_mes(cfg, [], previos)
    assert base == D("2100.00")
    assert estimada is True


def test_la_media_divide_entre_los_meses_que_tuvieron_ingresos():
    """El primer mes de uso solo hay un mes previo: dividir entre 3 daria una
    base ridicula y todos los botes en rojo desde el minuto uno."""
    cfg = config(base_mode="real", ingreso_base=None)
    previos = [ingreso("2000.00", date(2026, 5, 5))]
    assert base_del_mes(cfg, [], previos) == (D("2000.00"), True)


def test_base_real_sin_nada_es_cero_y_estimada():
    cfg = config(base_mode="real", ingreso_base=None)
    assert base_del_mes(cfg, [], []) == (D("0.00"), True)


def test_dia_1_sin_datos_no_revienta():
    """Division por cero al calcular el ritmo: el dia 1 y sin nada registrado."""
    cfg = config(base_mode="real", ingreso_base=None)
    resumen = calcular_resumen(cfg, [], [], [], [], date(2026, 2, 1))
    assert resumen["dias_mes"] == 28
    assert resumen["dias_restantes"] == 27
    assert resumen["base"] == D("0.00")
    assert all(b["estado"] == "verde" for b in resumen["botes"])


def test_resumen_cuenta_los_dias_del_mes_reales():
    resumen = calcular_resumen(config(), [], [], [], [], date(2024, 2, 10))
    assert resumen["dias_mes"] == 29      # bisiesto


# -- Toca cargar este recurrente? --------------------------------------------

def test_mensual_toca_a_partir_de_su_dia():
    r = rec("60.00", "mensual", dia_cargo=15)
    assert toca_cargar(r, date(2026, 6, 10)) is False
    assert toca_cargar(r, date(2026, 6, 15)) is True


def test_anual_solo_en_su_mes():
    r = rec("480.00", "anual", mes_cargo=3, dia_cargo=10)
    assert toca_cargar(r, date(2026, 3, 12)) is True
    assert toca_cargar(r, date(2026, 3, 5)) is False
    assert toca_cargar(r, date(2026, 4, 12)) is False


def test_trimestral_repite_cada_tres_meses():
    r = rec("90.00", "trimestral", mes_cargo=3, dia_cargo=1)
    for mes, toca in [(3, True), (4, False), (6, True), (9, True), (12, True)]:
        assert toca_cargar(r, date(2026, mes, 5)) is toca


def test_recurrente_apagado_nunca_toca():
    r = rec("60.00", "mensual", dia_cargo=1, activo=False)
    assert toca_cargar(r, date(2026, 6, 20)) is False
