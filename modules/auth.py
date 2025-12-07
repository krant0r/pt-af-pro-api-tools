import asyncio
import base64
import json
import time
from typing import Dict, Optional, Any

import httpx
from loguru import logger

from .config import config


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _jwt_exp(access_token: str) -> Optional[int]:
    """Достаём поле exp из JWT access-токена (если оно есть)."""
    try:
        parts = access_token.split(".")
        if len(parts) != 3:
            return None
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        return int(payload.get("exp"))
    except Exception:
        return None


class TokenManager:
    """Управление base-токенами и per-tenant токенами.

    * base_access / base_refresh — токены уровня "всего инстанса"
      (используются, в частности, в init_snapshots / snapshots.py).
    * self.tenants[tenant_id] = {"access", "refresh", "exp", "lock"}
      — токены для конкретного тенанта.
    """

    def __init__(self) -> None:
        self.base_access: Optional[str] = None
        self.base_refresh: Optional[str] = None

        # per-tenant: { tenant_id: {"access": str|None, "refresh": str|None, "exp": int, "lock": asyncio.Lock()} }
        self.tenants: Dict[str, Dict[str, Any]] = {}

        # Защита инициализации и глобального refresh'а
        self._init_lock = asyncio.Lock()
        self._base_refresh_lock = asyncio.Lock()

    # ───────────────────── базовая авторизация ─────────────────────

    async def get_initial_tokens(self) -> bool:
        """Первичная авторизация.

        Варианты:
        * если задан API_TOKEN -> просто используем его как base_access;
        * иначе логинимся по API_LOGIN/API_PASSWORD на /auth/refresh_tokens.
        """
        logger.info("Starting authentication")

        # 1) Токен из переменной/sekreta
        if config.API_TOKEN:
            self.base_access = config.API_TOKEN
            self.base_refresh = None
            logger.success("Auth successful (static API_TOKEN)")
            return True

        # 2) Логин/пароль
        if not (config.API_LOGIN and config.API_PASSWORD):
            logger.error("Auth failed: no API_TOKEN and no API_LOGIN/API_PASSWORD provided")
            return False

        url = f"{config.AF_URL}/api/ptaf/v4/auth/refresh_tokens"
        payload: Dict[str, Any] = {
            "username": config.API_LOGIN,
            "password": config.API_PASSWORD,
            "fingerprint": "python",
        }
        # LDAP флаг:
        #   LDAP_AUTH не задан  -> ldap в payload НЕ добавляем;
        #   LDAP_AUTH=True      -> ldap: true;
        #   LDAP_AUTH=False     -> ldap: false.
        if config.LDAP_AUTH is not None:
            payload["ldap"] = config.LDAP_AUTH

        try:
            async with httpx.AsyncClient(
                verify=config.VERIFY_SSL,
                timeout=config.REQUEST_TIMEOUT,
            ) as client:
                r = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                r.raise_for_status()
                data: Dict[str, Any] = r.json()

            self.base_access = data.get("access_token")
            self.base_refresh = data.get("refresh_token")
            if not self.base_access:
                logger.error("Auth failed: no access_token in response")
                return False

            logger.success(
                "Auth successful (password%s)"
                % (" + LDAP" if payload.get("ldap") else "")
            )
            return True
        except Exception as e:
            logger.error(f"Auth failed: {e}")
            return False

    async def ensure_base_token(self, client: Optional[httpx.AsyncClient] = None) -> str:
        """Backwards-совместимая обёртка для старого snapshots.py.

        * Гарантирует наличие base_access.
        * Параметр client оставлен только ради сигнатуры — мы его не используем.
        """
        if self.base_access:
            return self.base_access

        async with self._init_lock:
            if self.base_access:
                return self.base_access

            ok = await self.get_initial_tokens()
            if not ok or not self.base_access:
                raise RuntimeError("Cannot obtain base access token")

            return self.base_access

    # ───────────────────── per-tenant токены ─────────────────────

    def _ensure_tenant_entry(self, tenant_id: str) -> None:
        if tenant_id not in self.tenants:
            self.tenants[tenant_id] = {
                "access": None,
                "refresh": None,
                "exp": 0,
                "lock": asyncio.Lock(),
            }

    async def refresh_tenant_tokens(self, tenant_id: str, force: bool = False) -> bool:
        """Обновить access/refresh для указанного тенанта.

        Логика:
        * если есть свой refresh у тенанта -> используем его;
        * если нет -> один общий base_refresh, с сериализацией через _base_refresh_lock;
        * base_refresh в entry["refresh"] НЕ копируем, чтобы не плодить копии.
        """
        self._ensure_tenant_entry(tenant_id)
        entry = self.tenants[tenant_id]

        async with entry["lock"]:
            now = int(time.time())
            if not force and entry["access"] and entry["exp"] - config.TOKEN_REFRESH_SKEW > now:
                return True

            async def _do_exchange(refresh_token: str) -> Optional[Dict[str, Any]]:
                payload: Dict[str, Any] = {
                    "refresh_token": refresh_token,
                    "tenant_id": tenant_id,
                    "fingerprint": "python",
                }
                async with httpx.AsyncClient(
                    verify=config.VERIFY_SSL,
                    timeout=config.REQUEST_TIMEOUT,
                ) as client:
                    r = await client.post(
                        f"{config.AF_URL}/api/ptaf/v4/auth/access_tokens",
                        json=payload,
                    )
                    r.raise_for_status()
                    return r.json()

            max_retries = getattr(config, "MAX_RETRIES", 3)

            for attempt in range(1, max_retries + 1):
                try:
                    if entry.get("refresh"):
                        # есть собственный refresh для этого tenant
                        data = await _do_exchange(entry["refresh"])
                        if not data:
                            raise RuntimeError("Empty response on tenant refresh")
                        new_tenant_refresh = data.get("refresh_token")
                        if new_tenant_refresh:
                            entry["refresh"] = new_tenant_refresh
                    else:
                        # используем общий base_refresh под глобальным локом
                        async with self._base_refresh_lock:
                            if not self.base_refresh:
                                logger.error(f"No base_refresh available for tenant {tenant_id}")
                                return False

                            data = await _do_exchange(self.base_refresh)
                            if not data:
                                raise RuntimeError("Empty response on base refresh")
                            new_base_refresh = data.get("refresh_token")
                            if new_base_refresh:
                                self.base_refresh = new_base_refresh
                            # ВАЖНО: base_refresh НЕ кладём в entry["refresh"]

                    if not data or "access_token" not in data:
                        raise RuntimeError("No access_token in refresh response")

                    entry["access"] = data["access_token"]
                    exp = _jwt_exp(entry["access"]) or (now + 600)
                    entry["exp"] = exp
                    has_own = bool(entry.get("refresh"))
                    logger.success(
                        f"Tokens refreshed for tenant {tenant_id} (own_refresh={has_own})"
                    )
                    return True

                except httpx.HTTPStatusError as e:
                    code = e.response.status_code if e.response else "unknown"
                    # Временные статусы — ретраим
                    if code in {409, 423, 429, 500, 502, 503, 504} and attempt < max_retries:
                        delay = min(2 ** (attempt - 1), 5)
                        logger.warning(
                            f"Refresh tenant {tenant_id} HTTP {code}, retry in {delay}s"
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.error(
                        f"Failed to refresh tokens for tenant {tenant_id}: HTTP {code}"
                    )
                    return False

                except (httpx.TimeoutException, httpx.TransportError) as e:
                    if attempt < max_retries:
                        delay = min(2 ** (attempt - 1), 5)
                        logger.warning(
                            f"Refresh tenant {tenant_id} {type(e).__name__}: {e!r}; retry in {delay}s"
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.error(
                        f"Failed to refresh tokens for tenant {tenant_id}: {type(e).__name__}"
                    )
                    return False

                except Exception as e:
                    if attempt < max_retries:
                        delay = min(2 ** (attempt - 1), 5)
                        logger.warning(
                            f"Refresh tenant {tenant_id} unexpected {type(e).__name__}: {e!r}; retry in {delay}s"
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.error(
                        f"Failed to refresh tokens for tenant {tenant_id}: {e!r}"
                    )
                    return False

            logger.error(
                f"Failed to refresh tokens for tenant {tenant_id}: exhausted retries"
            )
            return False

    async def ensure_access_token(self, tenant_id: str) -> str:
        """Гарантирует access-токен для тенанта (или бросает исключение)."""
        self._ensure_tenant_entry(tenant_id)
        ok = await self.refresh_tenant_tokens(tenant_id, force=False)
        if not ok:
            raise RuntimeError(f"Cannot ensure access token for tenant {tenant_id}")
        return self.tenants[tenant_id]["access"]  # type: ignore[return-value]


class TenantAuth(httpx.Auth):
    """httpx.Auth, который автоматически подставляет Bearer для tenant.

    В этом проекте напрямую почти не используется, но оставлен для совместимости
    и потенциального использования в сторонних клиентах.
    """

    requires_request_body = True
    requires_response_body = True

    def __init__(self, token_manager: TokenManager, tenant_id: str) -> None:
        self.tm = token_manager
        self.tenant_id = tenant_id

    async def auth_flow(self, request):
        access = await self.tm.ensure_access_token(self.tenant_id)
        request.headers["Authorization"] = f"Bearer {access}"
        response = yield request

        if response.status_code == 401:
            # Принудительный refresh + один повтор
            ok = await self.tm.refresh_tenant_tokens(self.tenant_id, force=True)
            if ok:
                request.headers["Authorization"] = (
                    f"Bearer {self.tm.tenants[self.tenant_id]['access']}"
                )
                yield request
