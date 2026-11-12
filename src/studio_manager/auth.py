from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Form, Header, HTTPException, Request, status


def _principal_for_token(request: Request, token: str | None) -> str:
    expected = request.app.state.settings.api_token
    if not token or not secrets.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="valid local bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "local-api-user"


def require_api_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    return _principal_for_token(request, token if scheme.lower() == "bearer" else None)


def require_ui_approval_actor(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    approval_token: Annotated[str | None, Form()] = None,
) -> str:
    """Authenticate an approval form without embedding/storing a token in the page.

    Programmatic UI clients may use Bearer auth. An explicitly supplied bad
    Authorization header never falls back to a form credential.
    """
    if authorization is not None:
        return require_api_token(request, authorization)
    return _principal_for_token(request, approval_token)
