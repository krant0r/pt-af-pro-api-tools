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

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Load .env if present (локальная разработка, в Docker не обязателен)
load_dotenv()


def _load_settings_file(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        # Не валидный JSON или другая ошибка — считаем, что настроек нет.
        pass
    return {}


def _write_settings_file(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
    if isinstance(val, bool):
        return val
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
        self.DATA_DIR: Path = self.BASE_DIR / "data"
        self.SETTINGS_FILE: Path = self.DATA_DIR / "settings.json"

        # ---------- Логирование ----------
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
        log_file = os.getenv(
            "LOG_FILE", str(self.BASE_DIR / "logs" / "ptaf-web.log")
        )
        self.LOG_FILE: Path = Path(log_file)

        # ---------- Загружаемые настройки ----------
        self.settings: Dict[str, Any] = {}

        # Создаём директории (в Docker обычно будут volume-ы)
        self.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Значения, которые могут обновляться после сохранения настроек.
        self.UI_THEME: str = "light"
        self.UI_LANGUAGE: str = "ru"
        self.AF_URL: str = ""
        self.API_PATH: str = ""
        self.VERIFY_SSL: Any = True
        self.REQUEST_TIMEOUT: float = 30.0
        self.API_TOKEN: str = ""
        self.API_LOGIN: str = ""
        self.API_PASSWORD: str = ""
        self.LDAP_AUTH: Optional[bool] = None
        self.TENANTS_ENDPOINT: str = ""
        self.SNAPSHOT_ENDPOINT: str = ""
        self.RULES_ENDPOINT: str = ""
        self.ACTIONS_ENDPOINT: str = ""
        self.SNAPSHOT_RETENTION_DAYS: Optional[int] = None

        self.SNAPSHOTS_DIR: Path = Path(
            os.getenv("SNAPSHOTS_DIR", str(self.BASE_DIR / "snapshots"))
        ).resolve()
        self.RULES_DIR: Path = Path(
            os.getenv("RULES_DIR", str(self.BASE_DIR / "rules"))
        ).resolve()
        self.ACTIONS_DIR: Path = Path(
            os.getenv("ACTIONS_DIR", str(self.BASE_DIR / "actions"))
        ).resolve()

        self.reload_from_sources()

        self.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        self.RULES_DIR.mkdir(parents=True, exist_ok=True)
        self.ACTIONS_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- internal helpers ----------

    def _get_setting(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        if key not in self.settings:
            return default
        val = self.settings.get(key)
        if isinstance(val, str):
            val = val.strip()
        return val

    def _settings_or_env(self, key: str, env_var: str, default: str = "") -> str:
        if key in self.settings:
            val = self._get_setting(key)
            return "" if val is None else str(val)
        return os.getenv(env_var, default)

    def _settings_or_secret(self, key: str, env_var: str, file_env_var: str) -> str:
        if key in self.settings:
            val = self._get_setting(key)
            return "" if val is None else str(val)
        return _read_secret(env_var, file_env_var)

    def _resolve_verify_ssl(self) -> Any:
        if "VERIFY_SSL" in self.settings:
            verify_ssl_env = self._get_setting("VERIFY_SSL")
        else:
            verify_ssl_env = "true"

        if isinstance(verify_ssl_env, bool):
            return verify_ssl_env

        lower = str(verify_ssl_env).strip().lower()
        if lower in {"true", "1", "yes", "on"}:
            return True
        if lower in {"false", "0", "no", "off"}:
            return False
        return verify_ssl_env

    def _resolve_retention_days(self) -> Optional[int]:
        if "SNAPSHOT_RETENTION_DAYS" in self.settings:
            raw_val = self._get_setting("SNAPSHOT_RETENTION_DAYS")
        else:
            raw_val = os.getenv("SNAPSHOT_RETENTION_DAYS", "30")

        try:
            retention_days = int(str(raw_val).strip())
            return retention_days if retention_days > 0 else None
        except (TypeError, ValueError):
            return None

    # ---------- public helpers ----------

    def reload_from_sources(self) -> None:
        """
        Загружает настройки из файла и окружения в порядке приоритета:
        1. data/settings.json (если ключ присутствует и не пустой)
        2. env / docker secrets
        3. значения по умолчанию
        """

        self.settings = _load_settings_file(self.SETTINGS_FILE)

        self.UI_THEME = self._get_setting("THEME", "light") or "light"
        self.UI_LANGUAGE = self._get_setting("LANGUAGE", "ru") or "ru"

        # ---------- Подключение к WAF API ----------
        # URL инстанса PTAF PRO, например "https://ptaf.example.com"
        self.AF_URL = self._settings_or_env("AF_URL", "AF_URL", "").rstrip("/")

        # Префикс API, обычно "/api/ptaf/v4"
        self.API_PATH = (
            self._settings_or_env("API_PATH", "API_PATH", "/api/ptaf/v4")
        ).rstrip("/")

        # SSL verification: "true"/"false" или путь до CA/cert
        self.VERIFY_SSL = self._resolve_verify_ssl()

        # Таймаут запросов
        self.REQUEST_TIMEOUT = float(
            self._settings_or_env("REQUEST_TIMEOUT", "REQUEST_TIMEOUT", "30")
        )

        # ---------- Auth credentials ----------
        # Статичный API token (если задан, username/password игнорируются)
        self.API_TOKEN = self._settings_or_secret(
            "API_TOKEN", "API_TOKEN", "API_TOKEN_FILE"
        )

        # Логин/пароль для JWT
        self.API_LOGIN = self._settings_or_secret(
            "API_LOGIN", "API_LOGIN", "API_LOGIN_FILE"
        )
        self.API_PASSWORD = self._settings_or_secret(
            "API_PASSWORD", "API_PASSWORD", "API_PASSWORD_FILE"
        )

        # Необязательный флаг LDAP:
        # LDAP_AUTH не задан     -> не отправляем "ldap"
        # LDAP_AUTH=true/1/...   -> "ldap": true
        # LDAP_AUTH=false/0/...  -> "ldap": false
        ldap_source = self._get_setting("LDAP_AUTH")
        self.LDAP_AUTH = _to_opt_bool(ldap_source)

        # ---------- Endpoints ----------
        # Список тенантов
        self.TENANTS_ENDPOINT = self._settings_or_env(
            "TENANTS_ENDPOINT", "TENANTS_ENDPOINT", f"{self.API_PATH}/auth/account/tenants"
        )

        # Глобальный снапшот конфигурации текущего тенанта
        self.SNAPSHOT_ENDPOINT = self._settings_or_env(
            "SNAPSHOT_ENDPOINT", "SNAPSHOT_ENDPOINT", f"{self.API_PATH}/config/snapshot"
        )

        # Эндпоинты для правил и действий (по умолчанию — типичные пути PTAF PRO)
        self.RULES_ENDPOINT = self._settings_or_env(
            "RULES_ENDPOINT", "RULES_ENDPOINT", f"{self.API_PATH}/config/rules"
        )
        self.ACTIONS_ENDPOINT = self._settings_or_env(
            "ACTIONS_ENDPOINT", "ACTIONS_ENDPOINT", f"{self.API_PATH}/config/actions"
        )

        retention_value = self._resolve_retention_days()
        self.SNAPSHOT_RETENTION_DAYS = retention_value

    def save_settings(self, updates: Dict[str, Any]) -> None:
        merged = {**self.settings, **updates}
        _write_settings_file(self.SETTINGS_FILE, merged)
        self.reload_from_sources()

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
