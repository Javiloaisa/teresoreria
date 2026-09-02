"""Genera un par de claves VAPID para las notificaciones push.

    python gen_vapid.py

Copia las dos líneas que imprime al .env del servidor y reinicia la API. Se
hace UNA VEZ: si se cambian las claves, todas las suscripciones que haya
dejan de valer y hay que volver a activar los avisos en cada móvil.
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def main() -> None:
    clave = ec.generate_private_key(ec.SECP256R1())
    privada = clave.private_numbers().private_value.to_bytes(32, "big")
    publica = clave.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    print("VAPID_PUBLIC_KEY=" + _b64url(publica))
    print("VAPID_PRIVATE_KEY=" + _b64url(privada))


if __name__ == "__main__":
    main()
