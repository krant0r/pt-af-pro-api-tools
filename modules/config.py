# modules/config.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv


# ───────────────────────── helpers ─────────────────────────

def _to_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on", "y", "t"}


def _to_opt_bool(val: Optional[str]) -> Optional[bool]:
    """Преобразует строку в Optional[bool].

    None/""        -> None
    "1,true,yes"   -> True
    "0,false,no"   -> False
    Любое другое    -> None (чтобы не сломать авторизацию).
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    s_low = s.lower()
    if s_low in {"1", "true", "yes", "on", "y", "t"}:
        return True
    if s_low in {"0", "false", "no", "off", "n", "f"}:
        return False
    return None


def _to_int(val: Optional[str], default: int = 0) -> int:
    try:
        return int(str(val).strip())
    except Exception:
        return default


def _to_float(val: Optional[str], default: float = 0.0) -> float:
    try:
        return float(str(val).strip())
    except Exception:
        return default


def _to_list(val: Optional[str]) -> List[str]:
    """Преобразует строку вида "a, b, c" в ["a","b","c"]."""
    if not val:
        return []
    parts = [p.strip() for p in str(val).split(",")]
    return [p for p in parts if p]


# ───────────────────────── config ─────────────────────────

class Config:
    """Единая точка настроек из .env (если есть), с безопасными дефолтами."""

    def __init__(self) -> None:
        # Загружаем .env из текущей директории (если есть)
        load_dotenv(override=False)

        # ── Логи
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
        # Совпадает с тем, что видно у вас в контейнере:
        self.LOG_FILE: Path = Path(os.getenv("LOG_FILE", "/home/app/af-pro-api.log")).resolve()

        # ── Файл для DataCollector (чтобы не падало на DATA_FILE)
        self.DATA_FILE: Path = Path(os.getenv("DATA_FILE", "/home/app/af-pro-api-data.json")).resolve()

        # ── Базовый URL API AF
        self.AF_URL: str = os.getenv("AF_URL", "https://example.invalid").rstrip("/")

        # ── Режимы
        self.VERIFY_SSL: bool = _to_bool(os.getenv("VERIFY_SSL"), True)
        # READ_ONLY учитывается: при True PATCH-запросы не выполняются, только логируются
        self.READ_ONLY: bool = _to_bool(os.getenv("READ_ONLY"), False)
        # Актуально только если ваш код читает/пишет локальный кеш
        self.LOAD_FROM_FILE: bool = _to_bool(os.getenv("LOAD_FROM_FILE"), False)

        # ── Фильтры итерации (имена, через запятую)
        self.ONLY_TENANTS: List[str] = _to_list(os.getenv("ONLY_TENANTS"))
        self.SKIP_TENANTS: List[str] = _to_list(os.getenv("SKIP_TENANTS"))
        self.ONLY_APPS: List[str] = _to_list(os.getenv("ONLY_APPS"))
        self.SKIP_APPS: List[str] = _to_list(os.getenv("SKIP_APPS"))

        # ── Пара действий для доп. пайплайна (можно оставить пустыми — тогда он пропустится)
        self.ACTION_ADD_NAME: str = (os.getenv("ACTION_ADD_NAME") or "").strip()
        self.ACTION_REMOVE_NAME: str = (os.getenv("ACTION_REMOVE_NAME") or "").strip()

        # ── SIEM action (используется в pipeline)
        self.SIEM_IP: str = os.getenv("SIEM_IP", "127.0.0.1")
        self.SIEM_PORT: int = _to_int(os.getenv("SIEM_PORT"), 1468)
        self.SIEM_ACTION_NAME: str = os.getenv("SIEM_ACTION_NAME", "Send to SIEM")

        # ── Тайминги/ретраи
        self.REQUEST_TIMEOUT: float = _to_float(os.getenv("REQUEST_TIMEOUT"), 30.0)
        self.PATCH_TIMEOUT: float = _to_float(os.getenv("PATCH_TIMEOUT"), 60.0)
        self.TOKEN_REFRESH_SKEW: int = _to_int(os.getenv("TOKEN_REFRESH_SKEW"), 120)
        self.MAX_RETRIES: int = _to_int(os.getenv("MAX_RETRIES"), 3)

        # ── Аутентификация
        # Можно хранить токен напрямую или через файл:
        #   API_TOKEN=...   ИЛИ   API_TOKEN_FILE=/run/secrets/api_token
        self.API_TOKEN: Optional[str] = self._read_api_token()
        self.API_LOGIN: str = os.getenv("API_LOGIN", "").strip()
        self.API_PASSWORD: str = os.getenv("API_PASSWORD", "").strip()

        # Для эндпойнта логина:
        #   LDAP_AUTH не задан  -> поле "ldap" в запросе НЕ отправляем
        #   LDAP_AUTH=true/1    -> "ldap": true
        #   LDAP_AUTH=false/0   -> "ldap": false
        self.LDAP_AUTH: Optional[bool] = _to_opt_bool(os.getenv("LDAP_AUTH"))

    # ── helpers ─────────────────────────────────────────────

    def _read_api_token(self) -> Optional[str]:
        """Можно хранить токен в отдельном файле (API_TOKEN_FILE), либо в переменной (API_TOKEN)."""
        token_file = os.getenv("API_TOKEN_FILE")
        if token_file:
            try:
                content = Path(token_file).read_text(encoding="utf-8").strip()
                if content:
                    return content
            except Exception:
                pass
        env_token = os.getenv("API_TOKEN")
        return env_token.strip() if env_token else None

    @property
    def auth_method(self) -> str:
        if self.API_TOKEN:
            return "token"
        if self.API_LOGIN and self.API_PASSWORD:
            return "password"
        raise ValueError("No auth credentials found: set API_TOKEN or API_LOGIN/API_PASSWORD")


config = Config()
