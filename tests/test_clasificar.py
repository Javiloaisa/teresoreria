"""Tests de la clasificación automática por reglas."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from clasificar import clasificar, normalizar  # noqa: E402


def r(id, patron, cat, prioridad=0, usos=0):
    return {"id": id, "patron": patron, "cat": cat, "prioridad": prioridad, "usos": usos}


def test_normalizar_quita_acentos_y_mayusculas():
    assert normalizar("  Cafetería   Ñora ") == "cafeteria nora"


def test_casa_pese_a_acentos_y_mayusculas():
    reglas = [r(1, "cafeteria", "deseo")]
    assert clasificar("Cafetería Ñora", reglas) == ("deseo", 1)


def test_casa_como_subcadena_en_concepto_de_banco():
    reglas = [r(1, "mercadona", "necesidad")]
    assert clasificar("COMPRA TARJ. MERCADONA 4512 VALENCIA", reglas) == ("necesidad", 1)


def test_gana_la_de_mas_prioridad():
    reglas = [
        r(1, "seguro", "necesidad", prioridad=10),
        r(2, "seguro de vida", "ahorro", prioridad=20),
    ]
    assert clasificar("Seguro de vida anual", reglas) == ("ahorro", 2)


def test_a_igual_prioridad_gana_la_mas_usada():
    reglas = [
        r(1, "amazon", "deseo", prioridad=10, usos=3),
        r(2, "amazon", "necesidad", prioridad=10, usos=40),
    ]
    assert clasificar("Amazon Marketplace", reglas) == ("necesidad", 2)


def test_sin_regla_que_case_no_decide():
    reglas = [r(1, "mercadona", "necesidad")]
    assert clasificar("Ferretería del barrio", reglas) == (None, None)


def test_concepto_vacio_no_revienta():
    assert clasificar("", [r(1, "mercadona", "necesidad")]) == (None, None)
    assert clasificar(None, []) == (None, None)


def test_patron_vacio_no_casa_con_todo():
    # Una regla con patrón en blanco casaría con cualquier cosa si no se filtra.
    assert clasificar("Mercadona", [r(1, "  ", "ahorro")]) == (None, None)


# -- El patron no puede quedar cortado a mitad de palabra ---------------------

def test_un_patron_corto_no_se_come_palabras_mas_largas():
    """La trampa de la subcadena pura: "bar" dentro de "barrio"."""
    reglas = [r(1, "bar", "deseo")]
    assert clasificar("Ferreteria del barrio", reglas) == (None, None)
    assert clasificar("Barberia Paco", reglas) == (None, None)
    assert clasificar("Compra en Barcelona", reglas) == (None, None)
    # Pero como bar de verdad sigue funcionando.
    assert clasificar("BAR MANOLO", reglas) == ("deseo", 1)
    assert clasificar("Cana en el bar", reglas) == ("deseo", 1)


def test_casa_con_conceptos_de_banco_pegados_a_numeros():
    """Los extractos vienen asi, y la regla tiene que reconocerlos igual."""
    reglas = [r(1, "mercadona", "necesidad")]
    assert clasificar("MERCADONA4512 VALENCIA", reglas) == ("necesidad", 1)
    assert clasificar("PAGO-MERCADONA/2026", reglas) == ("necesidad", 1)


def test_el_patron_puede_estar_al_final_del_todo():
    reglas = [r(1, "netflix", "deseo")]
    assert clasificar("Suscripcion netflix", reglas) == ("deseo", 1)


def test_el_plural_si_casa():
    """"seguro" tiene que reconocer "SEGUROS MAPFRE"; es lo que pone el banco."""
    assert clasificar("SEGUROS MAPFRE", [r(1, "seguro", "necesidad")]) == ("necesidad", 1)
    assert clasificar("Fondos indexados", [r(1, "fondo", "ahorro")]) == ("ahorro", 1)
    assert clasificar("Inversiones", [r(1, "inversion", "ahorro")]) == ("ahorro", 1)


def test_pero_el_plural_no_abre_la_mano_a_cualquier_cosa():
    reglas = [r(1, "bar", "deseo")]
    assert clasificar("Barba y afeitado", reglas) == (None, None)
    assert clasificar("Luzon Servicios", [r(1, "luz", "necesidad")]) == (None, None)
    # "gas" no debe comerse "gasolina" (que ya tiene su propia regla)
    assert clasificar("Gasolina Repsol", [r(1, "gas", "necesidad")]) == (None, None)
