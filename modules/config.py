from __future__ import annotations

"""
Central configuration for pt-af-pro-api-tools.

Все значения берутся из переменных окружения, чтобы код можно было безопасно
использовать в Docker / docker-compose и на bare metal.

Секреты (tokens / пароли) ожидаются либо:
- напрямую через env, например API_PASSWORD=...;
- либо через пары вида API_PASSWORD_FILE=/run/secrets/waf_api_password.
В этом случае читается содержимое файла.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env if present (локальная разработка, в Docker не обязателен)
load_dotenv()


def _to_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on", "y", "t"}


def _to_opt_bool(val: Optional[str]) -> Optional[bool]:
    """
    Троичное bool-значение:
    None / ""         -> None
    "1,true,yes,on"   -> True
    "0,false,no,off"  -> False
    мусор             -> None (fail-safe)
    """
    if val is None:
        return None
    s = val.strip()
    if not s:
        return None
    low = s.lower()
    if low in {"1", "true", "yes", "on", "y", "t"}:
        return True
    if low in {"0", "false", "no", "off", "n", "f"}:
        return False
    return None


def _read_secret(var_name: str, file_var_name: str) -> str:
    """
    Helper для чтения секретов в Docker-friendly стиле.

    Приоритет:
      1. *_FILE env с путём до файла.
      2. Обычная переменная окружения.

    Возвращает "" если ничего не найдено.
    """
    file_path = os.getenv(file_var_name)
    if file_path:
        try:
            content = Path(file_path).read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception:
            # не падаем, просто откатываемся к обычному env
            pass

    return (os.getenv(var_name) or "").strip()


class Config:
    def __init__(self) -> None:
        # ---------- Базовые пути ----------
        self.BASE_DIR: Path = Path(__file__).resolve().parent.parent

        # ---------- Логирование ----------
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
        log_file = os.getenv(
            "LOG_FILE", str(self.BASE_DIR / "logs" / "ptaf-web.log")
        )
        self.LOG_FILE: Path = Path(log_file)

        # ---------- Подключение к WAF API ----------
        # URL инстанса PTAF PRO, например "https://ptaf.example.com"
        self.AF_URL: str = os.getenv("AF_URL", "").rstrip("/")

        # Префикс API, обычно "/api/ptaf/v4"
        self.API_PATH: str = os.getenv("API_PATH", "/api/ptaf/v4").rstrip("/")

        # SSL verification: "true"/"false" или путь до CA/cert
        verify_ssl_env = os.getenv("VERIFY_SSL", "true")
        lower = verify_ssl_env.strip().lower()
        if lower in {"true", "1", "yes", "on"}:
            self.VERIFY_SSL = True
        elif lower in {"false", "0", "no", "off"}:
            self.VERIFY_SSL = False
        else:
            # трактуем как путь до CA/cert
            self.VERIFY_SSL = verify_ssl_env

        # Таймаут запросов
        self.REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "30"))

        # ---------- Auth credentials ----------
        # Статичный API token (если задан, username/password игнорируются)
        self.API_TOKEN: str = _read_secret("API_TOKEN", "API_TOKEN_FILE")

        # Логин/пароль для JWT
        self.API_LOGIN: str = _read_secret("API_LOGIN", "API_LOGIN_FILE")
        self.API_PASSWORD: str = _read_secret("API_PASSWORD", "API_PASSWORD_FILE")

        # Необязательный флаг LDAP:
        # LDAP_AUTH не задан     -> не отправляем "ldap"
        # LDAP_AUTH=true/1/...   -> "ldap": true
        # LDAP_AUTH=false/0/...  -> "ldap": false
        self.LDAP_AUTH: Optional[bool] = _to_opt_bool(os.getenv("LDAP_AUTH"))

        # ---------- Endpoints ----------
        # Список тенантов
        self.TENANTS_ENDPOINT: str = os.getenv(
            "TENANTS_ENDPOINT", f"{self.API_PATH}/auth/account/tenants"
        )

        # Глобальный снапшот конфигурации текущего тенанта
        self.SNAPSHOT_ENDPOINT: str = os.getenv(
            "SNAPSHOT_ENDPOINT", f"{self.API_PATH}/config/snapshot"
        )

        # Эндпоинты для правил и действий (по умолчанию — типичные пути PTAF PRO)
        self.RULES_ENDPOINT: str = os.getenv(
            "RULES_ENDPOINT", f"{self.API_PATH}/config/rules"
        )
        self.ACTIONS_ENDPOINT: str = os.getenv(
            "ACTIONS_ENDPOINT", f"{self.API_PATH}/config/actions"
        )

        # ---------- Директории для JSON-экспортов ----------
        self.SNAPSHOTS_DIR: Path = Path(
            os.getenv("SNAPSHOTS_DIR", str(self.BASE_DIR / "snapshots"))
        ).resolve()

        self.RULES_DIR: Path = Path(
            os.getenv("RULES_DIR", str(self.BASE_DIR / "rules"))
        ).resolve()

        self.ACTIONS_DIR: Path = Path(
            os.getenv("ACTIONS_DIR", str(self.BASE_DIR / "actions"))
        ).resolve()

        # Создаём директории (в Docker обычно будут volume-ы)
        self.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        self.RULES_DIR.mkdir(parents=True, exist_ok=True)
        self.ACTIONS_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def auth_method(self) -> str:
        """
        Какой метод авторизации включён:
          - "token"    — статичный API_TOKEN
          - "password" — username/password (JWT)

        Бросает исключение, если ничего не задано.
        """
        if self.API_TOKEN:
            return "token"
        if self.API_LOGIN and self.API_PASSWORD:
            return "password"
        raise ValueError(
            "No auth credentials configured. "
            "Set API_TOKEN or API_LOGIN/API_PASSWORD (or *_FILE variants)."
        )


config = Config()
