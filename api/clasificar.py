"""Clasificación automática de gastos por reglas de texto.

Sin IA a propósito: con 30 o 40 reglas queda cubierto el grueso del gasto real
y el comportamiento es **predecible**, que es justo lo que se quiere en una
herramienta de números. La app aprende sola cada vez que se corrige a mano la
categoría de un gasto y se acepta guardar la regla.
"""

import re
import unicodedata
from typing import Iterable, Optional


def normalizar(texto: Optional[str]) -> str:
    """minúsculas, sin acentos, espacios colapsados.

    Se aplica igual al concepto y al patrón, así que "Cafetería" y "cafeteria"
    son la misma cosa a efectos de búsqueda.
    """
    if not texto:
        return ""
    plano = unicodedata.normalize("NFKD", texto.strip().lower())
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plano)


# Lo único que se le consiente a un patrón por detrás: la marca del plural.
_PLURALES = ("", "s", "es")


def casa(patron: str, texto: str) -> bool:
    """Si `patron` aparece en `texto` sin quedar cortado a mitad de palabra.

    Es coincidencia de subcadena, pero la palabra tiene que terminar donde
    termina el patrón (o seguir solo con la 's' o 'es' del plural). Sin eso, la
    regla `bar` mandaría a Deseos la "Ferretería del barrio", la barbería y
    cualquier compra en Barcelona, que es justo la clase de sorpresa que no se
    quiere en una herramienta de números. Y con el plural permitido, `seguro`
    sigue reconociendo "SEGUROS MAPFRE".

    Por delante no se comprueba nada: los conceptos de banco vienen pegados a
    códigos ("PAGO-MERCADONA4512") y ahí el patrón tiene que casar igual.
    """
    desde = texto.find(patron)
    while desde != -1:
        resto = texto[desde + len(patron):]
        for sufijo in _PLURALES:
            if resto.startswith(sufijo):
                cola = resto[len(sufijo):]
                if not cola or not cola[0].isalpha():
                    return True
        desde = texto.find(patron, desde + 1)
    return False


def orden_reglas(reglas: Iterable[dict]) -> list[dict]:
    """Prioridad descendente y, a igualdad, las más usadas primero."""
    return sorted(
        reglas,
        key=lambda r: (-int(r.get("prioridad", 0)), -int(r.get("usos", 0)), r.get("id", 0)),
    )


def clasificar(concepto: str, reglas: Iterable[dict]) -> tuple[Optional[str], Optional[int]]:
    """Devuelve `(categoria, regla_id)` de la primera regla que case, o
    `(None, None)` si ninguna lo hace (entonces decide el usuario)."""
    texto = normalizar(concepto)
    if not texto:
        return None, None

    for regla in orden_reglas(reglas):
        patron = normalizar(regla.get("patron"))
        if patron and casa(patron, texto):
            return regla["cat"], regla.get("id")

    return None, None
