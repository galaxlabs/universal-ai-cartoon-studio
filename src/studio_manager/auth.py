from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, Request, status


def require_api_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    expected = request.app.state.settings.api_token
    if scheme.lower() != "bearer" or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="valid local bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "local-api-user"
