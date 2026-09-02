"""Envío de notificaciones Web Push (VAPID) con pywebpush.

Las claves van en variables de entorno, las dos en base64url y en una línea:

  VAPID_PUBLIC_KEY   la pública; el navegador la usa como applicationServerKey
  VAPID_PRIVATE_KEY  la privada en crudo (32 bytes en base64url)
  VAPID_SUBJECT      "mailto:tu@correo", contacto para el servicio de push

Se genera un par con `python gen_vapid.py`. Si no están puestas, la app
funciona igual: simplemente no hay avisos.
"""

import json
import os
from typing import Any

from pywebpush import WebPushException, webpush

# Cuando el navegador tira la suscripción (desinstalas la app, limpias datos),
# el servicio de push responde con esto y la fila ya no sirve para nada.
CADUCADA = (404, 410)


def clave_publica() -> str:
    return os.environ.get("VAPID_PUBLIC_KEY", "")


def _clave_privada() -> str | None:
    return os.environ.get("VAPID_PRIVATE_KEY") or None


def _sujeto() -> str:
    return os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com")


def configurado() -> bool:
    return bool(clave_publica() and _clave_privada())


def enviar(suscripcion: dict[str, Any], titulo: str, cuerpo: str,
           url: str = "/") -> tuple[bool, int]:
    """Manda un aviso. Devuelve `(enviado, codigo_http)`.

    Un código de `CADUCADA` significa que hay que borrar la suscripción.
    """
    clave = _clave_privada()
    if not clave:
        return False, 0

    try:
        webpush(
            subscription_info=suscripcion,
            data=json.dumps({"titulo": titulo, "cuerpo": cuerpo, "url": url}),
            vapid_private_key=clave,
            vapid_claims={"sub": _sujeto()},
            timeout=10,
        )
        return True, 201
    except WebPushException as e:
        return False, e.response.status_code if e.response is not None else 0
