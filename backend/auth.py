import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.db import get_user_by_username
from backend.models import User

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey_for_dev_only")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

ROLES_VALIDOS = {"administrador", "control_mision", "observador"}

# ── Modo de acceso ──────────────────────────────────────────────────────────
#
# `REQUIRE_LOGIN=false` permite que el dashboard publico entre sin credenciales.
# NO se elimina el sistema de roles: el rol por defecto sigue decidiendo que
# datos se ven (biometricos restringidos, umbrales solo para administrador).
# Es el modo de pruebas con sensores formales; para produccion, dejar en "true".
REQUIRE_LOGIN = os.getenv("REQUIRE_LOGIN", "true").strip().lower() not in ("false", "0", "no")
DEFAULT_ROL = os.getenv("DEFAULT_ROL", "administrador").strip()
DEFAULT_USERNAME = os.getenv("DEFAULT_USERNAME", "anonimo").strip()
if DEFAULT_ROL not in ROLES_VALIDOS:
    DEFAULT_ROL = "observador"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Emite un JWT que incluye el claim 'rol'."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_payload(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> User:
    """
    Dependency FastAPI: valida JWT y devuelve el User con su rol.

    Si `REQUIRE_LOGIN=false`, acepta la peticion sin token y devuelve un
    usuario sintetico con `DEFAULT_ROL`. El filtrado por rol se mantiene
    intacto — lo que cambia es solo si hay que presentar credenciales.
    """
    if not REQUIRE_LOGIN:
        if token:
            # Si viene un token valido, se respeta su rol (no se degrada).
            payload = _decode_payload(token)
            if payload is not None:
                username = payload.get("sub")
                if username:
                    user_dict = get_user_by_username(username)
                    if user_dict is not None:
                        return User(**user_dict)
        return User(id=0, username=DEFAULT_USERNAME, rol=DEFAULT_ROL)

    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise exc
    payload = _decode_payload(token)
    if payload is None:
        raise exc
    username: str = payload.get("sub")
    if username is None:
        raise exc
    user_dict = get_user_by_username(username)
    if user_dict is None:
        raise exc
    return User(**user_dict)


def get_user_from_token(token: str) -> Optional[User]:
    """Extrae el User desde el token JWT sin levantar excepcion (para WebSocket)."""
    payload = _decode_payload(token)
    if payload is None:
        return None
    username: str = payload.get("sub")
    if not username:
        return None
    user_dict = get_user_by_username(username)
    if not user_dict:
        return None
    return User(**user_dict)


def authenticate_user(username: str, password: str) -> Optional[User]:
    user_dict = get_user_by_username(username)
    if not user_dict:
        return None
    if not verify_password(password, user_dict["password_hash"]):
        return None
    return User(**user_dict)


def require_role(*roles: str):
    """
    Dependency factory: lanza 403 si el usuario autenticado no tiene uno de los
    roles indicados.

    Uso:
        @app.get("/admin/...", dependencies=[Depends(require_role("administrador"))])
    """
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere uno de: {roles}",
            )
        return current_user
    return _check
