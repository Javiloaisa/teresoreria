"""Qué avisar y con qué texto.

Módulo **puro**: recibe el resumen ya calculado y lo que se ha avisado este mes,
y decide qué mandar. No toca la base ni envía nada; de eso se encarga
`index.py`. Así se puede probar la parte delicada, que es el antispam.

La regla de oro es que un aviso que se repite deja de leerse. Un aviso por
bote, nivel y mes, y ya está.
"""

from decimal import Decimal
from typing import Iterable

NOMBRE_CAT = {
    "necesidad": "Necesidades",
    "deseo": "Deseos",
    "ahorro": "Ahorro",
}

# Verde no avisa: no hay nada que contar.
NIVELES = {"amarillo": "amarillo", "rojo": "rojo"}


def euros(valor) -> str:
    """340 € — sin céntimos, que en un aviso solo estorban."""
    entero = int(Decimal(str(valor)).to_integral_value())
    return f"{entero:,}".replace(",", ".") + " €"


def cuenta_dias(dias: int) -> str:
    if dias <= 0:
        return "Es el último día del mes."
    if dias == 1:
        return "Queda 1 día."
    return f"Quedan {dias} días."


def texto(bote: dict, dias_restantes: int) -> tuple[str, str]:
    """El aviso, corto y accionable, como en el encargo:

        Deseos: vas camino de 340 € y el tope son 300 €. Quedan 11 días.
    """
    nombre = NOMBRE_CAT[bote["cat"]]
    tope = euros(bote["presupuesto"])
    dias = cuenta_dias(dias_restantes)

    # Distinguir la previsión del hecho consumado importa: no es lo mismo
    # "vas camino de pasarte" que "ya te has pasado", y la reacción es otra.
    if bote["gastado"] > bote["presupuesto"]:
        return (
            f"{nombre}: te has pasado",
            f"Llevas {euros(bote['gastado'])} y el tope son {tope}. {dias}",
        )

    encabezado = "te vas a pasar" if bote["estado"] == "rojo" else "vas justo"
    return (
        f"{nombre}: {encabezado}",
        f"Vas camino de {euros(bote['proyeccion'])} y el tope son {tope}. {dias}",
    )


def decidir(resumen: dict, ya_enviados: Iterable[tuple[str, str]]) -> dict:
    """Qué mandar y qué rearmar, a la vista del mes en curso.

    - `enviar`: avisos que tocan y que no se han mandado ya este mes.
    - `rearmar`: botes que han vuelto a verde. Se borran sus filas para que,
      si vuelven a subir, el aviso salte otra vez. Sin esto, un bote que se
      arregla y se vuelve a torcer nunca volvería a avisar.
    """
    enviados = set(ya_enviados)
    enviar, rearmar = [], []

    # Sin base no hay nada que juzgar. Con el presupuesto a cero, cualquier
    # gasto deja el bote en rojo y saldrían tres avisos de "te has pasado" que
    # solo significan que aún no has declarado el ingreso del mes. La pantalla
    # ya lo dice; el móvil no tiene por qué dar la lata con ello.
    if resumen.get("base", 0) <= 0:
        return {"enviar": [], "rearmar": []}

    for bote in resumen["botes"]:
        cat, estado = bote["cat"], bote["estado"]

        if estado == "verde":
            if any(c == cat for c, _ in enviados):
                rearmar.append(cat)
            continue

        # Los primeros días del mes el estado se pinta pero no se notifica:
        # con tres días de datos la proyección es ruido puro.
        if not bote["avisable"]:
            continue

        nivel = NIVELES[estado]
        if (cat, nivel) in enviados:
            continue

        titulo, cuerpo = texto(bote, resumen["dias_restantes"])
        enviar.append({"cat": cat, "nivel": nivel, "titulo": titulo, "cuerpo": cuerpo})

    return {"enviar": enviar, "rearmar": rearmar}
