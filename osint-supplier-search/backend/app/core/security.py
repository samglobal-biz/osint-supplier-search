from __future__ import annotations
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.utils import base64url_decode
import json, base64
from app.config import settings

bearer = HTTPBearer(auto_error=False)

# Supabase JWKS public key (ES256) — fetched from /auth/v1/.well-known/jwks.json
_SUPABASE_JWKS = {
    "keys": [{
        "alg": "ES256", "crv": "P-256", "kty": "EC", "use": "sig",
        "kid": "6537d7fb-72fc-49c4-84c8-42a172e1df26",
        "x": "VtRkL2FE-fo0dr11riNPIidAe6UIcRIz1eSAPlbkUAo",
        "y": "VTOpBQYkYLGrN4RGMGDuqzCOtqPh2hP3oRo9KDxCAoE",
    }]
}


def _get_key(token: str):
    """Return the right key for this token: ES256 JWK or HS256 secret."""
    try:
        header = json.loads(base64.b64decode(token.split(".")[0] + "==").decode())
    except Exception:
        return settings.supabase_jwt_secret
    if header.get("alg") == "ES256":
        return _SUPABASE_JWKS["keys"][0]
    return settings.supabase_jwt_secret


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
) -> str:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = credentials.credentials
    try:
        key = _get_key(token)
        alg = "ES256" if isinstance(key, dict) else "HS256"
        payload = jwt.decode(token, key, algorithms=[alg], audience="authenticated")
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
