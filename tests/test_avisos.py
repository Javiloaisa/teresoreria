"""Tests del motor de avisos.

Lo que hay que blindar aquí es el antispam. Un aviso que se repite deja de
leerse, y una app de dinero que no se lee no sirve para nada.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

import pytest  # noqa: E402

from avisos import cuenta_dias, decidir, euros, texto  # noqa: E402


def bote(cat="deseo", estado="rojo", presupuesto=300, gastado=200,
         proyeccion=340, avisable=True):
    return {
        "cat": cat, "estado": estado, "presupuesto": presupuesto,
        "gastado": gastado, "proyeccion": proyeccion, "avisable": avisable,
    }


def resumen(*botes, dias_restantes=11):
    return {"botes": list(botes), "dias_restantes": dias_restantes}


# -- El texto del aviso ------------------------------------------------------

def test_el_aviso_es_el_del_encargo():
    titulo, cuerpo = texto(bote(), dias_restantes=11)
    assert titulo == "Deseos: te vas a pasar"
    assert cuerpo == "Vas camino de 340 € y el tope son 300 €. Quedan 11 días."


def test_avisa_distinto_cuando_ya_te_has_pasado():
    """No es lo mismo "vas camino" que "ya está hecho": la reacción es otra."""
    titulo, cuerpo = texto(
        bote(gastado=350, proyeccion=420), dias_restantes=5)
    assert titulo == "Deseos: te has pasado"
    assert cuerpo.startswith("Llevas 350 € y el tope son 300 €")


def test_el_ambar_no_alarma():
    titulo, _ = texto(bote(estado="amarillo", proyeccion=290), dias_restantes=8)
    assert titulo == "Deseos: vas justo"


@pytest.mark.parametrize("dias,esperado", [
    (11, "Quedan 11 días."), (2, "Quedan 2 días."),
    (1, "Queda 1 día."), (0, "Es el último día del mes."),
])
def test_cuenta_de_dias(dias, esperado):
    assert cuenta_dias(dias) == esperado


def test_los_importes_van_sin_centimos():
    assert euros(340) == "340 €"
    assert euros("1234.56") == "1.235 €"


# -- Antispam ----------------------------------------------------------------

def test_avisa_una_vez_por_bote_nivel_y_mes():
    r = resumen(bote())
    primero = decidir(r, [])
    assert [a["cat"] for a in primero["enviar"]] == ["deseo"]

    # Al día siguiente, mismo estado: no se repite.
    segundo = decidir(r, [("deseo", "rojo")])
    assert segundo["enviar"] == []


def test_de_ambar_a_rojo_si_vuelve_a_avisar():
    """Empeorar es noticia: el ámbar ya avisado no tapa el rojo."""
    r = resumen(bote(estado="rojo"))
    salida = decidir(r, [("deseo", "amarillo")])
    assert [a["nivel"] for a in salida["enviar"]] == ["rojo"]


def test_de_rojo_a_ambar_no_avisa_otra_vez():
    """Mejorar dentro del aviso no es noticia: el ámbar ya se mandó antes."""
    r = resumen(bote(estado="amarillo"))
    salida = decidir(r, [("deseo", "amarillo"), ("deseo", "rojo")])
    assert salida["enviar"] == []


def test_volver_a_verde_rearma_el_aviso():
    """Si el bote se arregla se borran sus filas; si se tuerce otra vez,
    vuelve a avisar. Sin esto, un mes solo podría avisarte una vez."""
    salida = decidir(resumen(bote(estado="verde")), [("deseo", "rojo")])
    assert salida["rearmar"] == ["deseo"]
    assert salida["enviar"] == []

    # Y ya rearmado (sin filas), si se tuerce otra vez, avisa.
    otra_vez = decidir(resumen(bote(estado="rojo")), [])
    assert len(otra_vez["enviar"]) == 1


def test_verde_sin_avisos_previos_no_rearma_nada():
    salida = decidir(resumen(bote(estado="verde")), [])
    assert salida == {"enviar": [], "rearmar": []}


def test_los_primeros_dias_del_mes_no_se_notifica():
    """El estado se pinta en pantalla, pero con tres días de datos la
    proyección es ruido y no se manda nada."""
    salida = decidir(resumen(bote(avisable=False)), [])
    assert salida["enviar"] == []


def test_cada_bote_avisa_por_su_cuenta():
    r = resumen(
        bote(cat="necesidad", estado="verde"),
        bote(cat="deseo", estado="rojo"),
        bote(cat="ahorro", estado="amarillo"),
    )
    salida = decidir(r, [])
    assert {a["cat"]: a["nivel"] for a in salida["enviar"]} == {
        "deseo": "rojo", "ahorro": "amarillo"}


def test_un_bote_que_se_arregla_no_afecta_a_los_demas():
    r = resumen(
        bote(cat="deseo", estado="verde"),
        bote(cat="ahorro", estado="rojo"),
    )
    salida = decidir(r, [("deseo", "rojo"), ("ahorro", "rojo")])
    assert salida["rearmar"] == ["deseo"]
    assert salida["enviar"] == []      # el de ahorro ya estaba avisado
