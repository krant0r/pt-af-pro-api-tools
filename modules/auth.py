from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from typing import Dict, Optional

import httpx
from loguru import logger

from .config import config


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _jwt_exp(access_token: str) -> Optional[int]:
    """
    Extracts "exp" claim from JWT access token (seconds since epoch).
    Returns None if token is not a JWT or has no exp.
    """
    try:
        parts = access_token.split(".")
        if len(parts) != 3:
            return None
        payload_b = _b64url_decode(parts[1])
        payload = json.loads(payload_b.decode("utf-8"))
        return int(payload.get("exp")) if "exp" in payload else None
    except Exception:
        return None


class TokenManager:
    """
    Manages PTAF PRO JWT tokens.

    Supports two modes:
    • Static API token (config.auth_method == "token")
    • Username/password based JWT with per-tenant access tokens.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

        # Fingerprint is required by PTAF PRO auth API
        self.fingerprint: str = str(uuid.uuid4()).replace("-", "")

        # Base (no-tenant) tokens
        self.base_access: Optional[str] = None
        self.base_refresh: Optional[str] = None
        self.base_exp: Optional[int] = None

        # Per-tenant tokens: tenant_id -> dict(access, refresh, exp)
        self.tenants: Dict[str, Dict[str, Optional[int]]] = {}

    # ---------- helpers ----------

    @property
    def api_base(self) -> str:
        return config.AF_URL + config.API_PATH

    async def _request_tokens_by_password(self, client: httpx.AsyncClient) -> bool:
        url = f"{self.api_base}/auth/refresh_tokens"
        payload: Dict[str, object] = {
            "username": config.API_LOGIN,
            "password": config.API_PASSWORD,
            "fingerprint": self.fingerprint,
        }

        # LDAP flag:
        #   LDAP_AUTH not set  -> do NOT send "ldap"
        #   LDAP_AUTH=True     -> send "ldap": true
        #   LDAP_AUTH=False    -> send "ldap": false
        if config.LDAP_AUTH is not None:
            payload["ldap"] = config.LDAP_AUTH

        logger.debug(f"Requesting tokens by password at {url} (ldap={payload.get('ldap')})")

        r = await client.post(url, json=payload)
        if r.status_code != 201:
            logger.error(f"Auth failed: {r.status_code} {r.text}")
            return False

        data = r.json()
        self.base_access = data.get("access_token")
        self.base_refresh = data.get("refresh_token")
        self.base_exp = _jwt_exp(self.base_access or "")

        ldap_suffix = " + LDAP" if payload.get("ldap") else ""
        logger.success(f"Auth successful (password{ldap_suffix})")
        return True

    async def _request_tokens_for_tenant(
        self,
        client: httpx.AsyncClient,
        tenant_id: str,
    ) -> bool:
        """
        Получить / обновить access-токен для конкретного tenant'а.

        Важно:
        - используем текущий self.base_refresh;
        - если успешно, ОБНОВЛЯЕМ self.base_refresh на новый refresh_token;
        - если получаем 422 invalid_token, один раз переавторизуемся по паролю
        (получаем новый base_refresh) и пробуем ещё раз.
        """
        # Убедимся, что базовый токен вообще есть
        if not self.base_refresh:
            logger.error("No refresh token, cannot obtain tenant token")
            return False

        url = f"{self.api_base}/auth/access_tokens"

        async def _do_request(refresh_token: str) -> httpx.Response:
            payload = {
                "refresh_token": refresh_token,
                "tenant_id": tenant_id,
                "fingerprint": self.fingerprint,
            }
            logger.debug(f"Requesting tenant token for {tenant_id} at {url}")
            return await client.post(url, json=payload)

        # Сначала пробуем с текущим self.base_refresh
        tried_reauth = False

        while True:
            r = await _do_request(self.base_refresh)
            if r.status_code == 201:
                data = r.json()
                access = data.get("access_token")
                refresh = data.get("refresh_token")
                exp = _jwt_exp(access or "")

                # Обновляем информацию по tenant'у
                self.tenants[tenant_id] = {
                    "access": access,
                    "refresh": refresh,
                    "exp": exp,
                }

                # КРИТИЧНО: обновляем base_refresh, как в старом проекте
                if refresh:
                    self.base_refresh = refresh

                logger.success(f"Tenant {tenant_id} token obtained")
                return True

            # Если refresh_token протух (422 invalid_token) — переавторизуемся по паролю и пробуем ещё раз
            if (
                r.status_code == 422
                and not tried_reauth
                and "invalid_token" in r.text
                and config.auth_method == "password"
            ):
                tried_reauth = True
                logger.warning(
                    f"Tenant auth failed for {tenant_id} with invalid refresh_token, "
                    f"re-authenticating base tokens and retrying..."
                )
                # Сбросим базовые токены и получим новые
                self.base_access = None
                self.base_refresh = None
                self.base_exp = None

                ok = await self._request_tokens_by_password(client)
                if not ok or not self.base_refresh:
                    logger.error(
                        "Re-authentication by password failed, cannot obtain tenant token"
                    )
                    return False

                # Пойдём по циклу ещё раз с новым self.base_refresh
                continue

            # Любая другая ошибка — логируем и выходим
            logger.error(
                f"Tenant auth failed for {tenant_id}: {r.status_code} {r.text}"
            )
            return False


    # ---------- public API ----------

    async def ensure_base_token(self, client: httpx.AsyncClient) -> Optional[str]:
        """
        Ensure that we have a valid base (no-tenant) access token.
        Returns access token string or None on failure.
        """
        if config.auth_method == "token":
            return config.API_TOKEN

        async with self._lock:
            now = int(time.time())
            # refresh when less than 30 seconds left
            if (
                self.base_access
                and self.base_exp
                and self.base_exp - now > 30
            ):
                return self.base_access

            ok = await self._request_tokens_by_password(client)
            return self.base_access if ok else None

    async def ensure_tenant_token(
        self,
        client: httpx.AsyncClient,
        tenant_id: str,
    ) -> Optional[str]:
        """
        Ensure that we have a valid access token for a given tenant.
        Returns access token string or None on failure.
        """
        if config.auth_method == "token":
            return config.API_TOKEN

        # Make sure base tokens exist
        await self.ensure_base_token(client)

        async with self._lock:
            info = self.tenants.get(tenant_id)
            now = int(time.time())

            if info:
                access = info.get("access")
                exp = info.get("exp")

                if access and isinstance(exp, int) and exp - now > 30:
                    return access  # type: ignore[return-value]



            ok = await self._request_tokens_for_tenant(client, tenant_id)
            if not ok:
                return None

            return self.tenants[tenant_id]["access"]  # type: ignore[index]



class TenantAuth(httpx.Auth):
    """
    httpx.Auth implementation which automatically injects Bearer token
    for a given tenant using TokenManager.
    """

    requires_response_body = True

    def __init__(self, token_manager: TokenManager, tenant_id: Optional[str]) -> None:
        self.tm = token_manager
        self.tenant_id = tenant_id

    async def async_auth_flow(self, request: httpx.Request):
        async with httpx.AsyncClient(
            verify=config.VERIFY_SSL,
            timeout=config.REQUEST_TIMEOUT,
        ) as client:
            token = await (
                self.tm.ensure_tenant_token(client, self.tenant_id)
                if self.tenant_id
                else self.tm.ensure_base_token(client)
            )
            if not token:
                raise httpx.HTTPError("Unable to obtain access token")

            request.headers["Authorization"] = f"Bearer {token}"
            response = yield request

            # On 401/403 we try once more (only for password auth)
            if response.status_code in (401, 403) and config.auth_method == "password":
                async with httpx.AsyncClient(
                    verify=config.VERIFY_SSL,
                    timeout=config.REQUEST_TIMEOUT,
                ) as client2:
                    if self.tenant_id:
                        logger.warning(
                            f"Auth challenge ({response.status_code}). Refreshing tenant token for {self.tenant_id}"
                        )
                        # Drop cached token to force refresh
                        self.tm.tenants.pop(self.tenant_id, None)
                        token = await self.tm.ensure_tenant_token(
                            client2, self.tenant_id
                        )
                    else:
                        logger.warning(
                            f"Auth challenge ({response.status_code}). Refreshing base token"
                        )
                        token = await self.tm.ensure_base_token(client2)

                    if token:
                        request.headers["Authorization"] = f"Bearer {token}"
                        yield request
