"""Genera los iconos PNG de la PWA.

    python scripts/gen_iconos.py

Sin dependencias: escribe el PNG a mano (zlib + struct) porque instalar Pillow
solo para tres iconos no compensa. El dibujo es el propio concepto de la app:
tres barras, una por bote, en verde, ámbar y rojo.

Solo hay que volver a ejecutarlo si se cambian los colores o el diseño; los PNG
resultantes van al repositorio.
"""

import struct
import zlib
from pathlib import Path

SALIDA = Path(__file__).resolve().parents[1] / "frontend" / "public"

FONDO = (0x12, 0x31, 0x2B)          # verde-tinta, oscuro y cálido
BARRAS = [
    ((0x4A, 0xDE, 0x80), 0.86),     # verde   — dentro de presupuesto
    ((0xFB, 0xBF, 0x24), 0.62),     # ámbar   — rozando el tope
    ((0xF8, 0x71, 0x71), 0.38),     # rojo    — pasado
]

SUPERMUESTREO = 3   # se dibuja a 3x y se promedia: bordes suaves sin librerías


def escribir_png(ruta: Path, ancho: int, alto: int, pixeles: list) -> None:
    crudo = b"".join(
        b"\x00" + bytes(canal for px in fila for canal in px) for fila in pixeles
    )

    def bloque(tipo: bytes, datos: bytes) -> bytes:
        return (struct.pack(">I", len(datos)) + tipo + datos
                + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF))

    ruta.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + bloque(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0))
        + bloque(b"IDAT", zlib.compress(crudo, 9))
        + bloque(b"IEND", b"")
    )


def _dentro_rect_redondeado(x, y, x0, y0, x1, y1, r) -> bool:
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def dibujar(lado: int, margen: float = 0.0) -> list:
    """Devuelve la matriz de píxeles RGBA del icono.

    `margen` es la fracción de lado que se deja libre alrededor del dibujo: los
    iconos maskable la necesitan porque Android les recorta las esquinas.
    """
    n = lado * SUPERMUESTREO
    dentro = margen * n
    util = n - 2 * dentro
    radio_fondo = util * 0.22

    # Las tres barras, centradas verticalmente y alineadas por la izquierda.
    alto_barra = util * 0.13
    hueco = util * 0.09
    total = 3 * alto_barra + 2 * hueco
    x_barra = dentro + util * 0.16
    y_primera = dentro + (util - total) / 2
    largo_max = util * 0.68

    filas = []
    for fy in range(lado):
        fila = []
        for fx in range(lado):
            sr = sg = sb = sa = 0
            for oy in range(SUPERMUESTREO):
                for ox in range(SUPERMUESTREO):
                    x = fx * SUPERMUESTREO + ox + 0.5
                    y = fy * SUPERMUESTREO + oy + 0.5
                    color = None

                    if _dentro_rect_redondeado(
                            x, y, dentro, dentro, dentro + util, dentro + util,
                            radio_fondo):
                        color = FONDO
                        for i, (rgb, largo) in enumerate(BARRAS):
                            y0 = y_primera + i * (alto_barra + hueco)
                            if _dentro_rect_redondeado(
                                    x, y, x_barra, y0,
                                    x_barra + largo_max * largo, y0 + alto_barra,
                                    alto_barra / 2):
                                color = rgb
                                break

                    if color:
                        sr += color[0]
                        sg += color[1]
                        sb += color[2]
                        sa += 255

            muestras = SUPERMUESTREO ** 2
            a = sa // muestras
            # Se promedia solo sobre las muestras pintadas: si no, los bordes
            # tiran a negro en vez de fundirse con la transparencia.
            pintadas = max(1, sa // 255)
            fila.append((sr // pintadas, sg // pintadas, sb // pintadas, a))
        filas.append(fila)
    return filas


ICONOS = [
    ("icon-192.png", 192, 0.0),
    ("icon-512.png", 512, 0.0),
    # Zona segura del 80 %: Android recorta el resto en los iconos maskable.
    ("icon-maskable-512.png", 512, 0.10),
]


if __name__ == "__main__":
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, lado, margen in ICONOS:
        escribir_png(SALIDA / nombre, lado, lado, dibujar(lado, margen))
        print(f"  {nombre}  ({lado}x{lado})")
    print("Iconos generados en", SALIDA)
