"""Autenticación: un solo usuario, contraseña y sesión larga.

La contraseña se guarda hasheada con argon2 (nunca en claro) y se crea con
`python manage.py set-password`. No hay registro, ni recuperación, ni roles:
es una app personal.

La sesión viaja en una cookie HttpOnly firmada con `SECRET_KEY`, así que el
navegador no puede manipularla y el JavaScript de la página no puede leerla.
Dura 60 días para no tener que entrar cada vez desde el móvil.
"""

import os

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "teresoreria_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 60  # 60 días

_ph = PasswordHasher()


def _secret() -> str:
    s = os.environ.get("SECRET_KEY")
    if not s:
        raise RuntimeError(
            "Falta la variable de entorno SECRET_KEY "
            "(clave para firmar la cookie de sesión)."
        )
    return s


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt="teresoreria-session")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        _ph.verify(password_hash, password)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def issue_cookie(response: Response) -> None:
    token = _serializer().dumps({"u": 1})
    # En local sobre http hay que poner COOKIE_SECURE=0; en producción se deja
    # en 1 para que la cookie solo viaje cifrada.
    secure = os.environ.get("COOKIE_SECURE", "1") != "0"
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def hay_sesion(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        _serializer().loads(token, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return True


def require_login(request: Request) -> None:
    """Dependencia de FastAPI: exige sesión válida."""
    if not hay_sesion(request):
        raise HTTPException(401, "Necesitas iniciar sesión.")
