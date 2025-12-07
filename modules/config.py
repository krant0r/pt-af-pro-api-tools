from __future__ import annotations

"""
Central configuration for pt-af-pro-api-tools.

All values are taken from environment variables so that the code
can be safely used in Docker / docker-compose and on bare metal.

Secrets (tokens / passwords) are expected to be passed either:
  - directly via env variables, e.g. API_PASSWORD=<value>; or
  - via "FILE" companions, e.g. API_PASSWORD_FILE=/run/secrets/waf_api_password

In the second case the file content is read and used as the value.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


# Load .env if present (useful for local development, not required in Docker)
load_dotenv()


def _to_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on", "y", "t"}


def _read_secret(var_name: str, file_var_name: str) -> str:
    """
    Helper for reading secrets in a Docker-friendly way.

    Priority:
      1. *_FILE env var pointing to file with secret.
      2. Plain env var.

    Returns empty string if nothing found.
    """
    file_path = os.getenv(file_var_name)
    if file_path:
        try:
            content = Path(file_path).read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception:
            # Do not crash on bad secret file, just fall back to env var
            pass
    return (os.getenv(var_name) or "").strip()


class Config:
    def __init__(self) -> None:
        # ---------- Basic paths ----------
        self.BASE_DIR: Path = Path(__file__).resolve().parent.parent

        # ---------- Logging ----------
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
        log_file = os.getenv("LOG_FILE", str(self.BASE_DIR / "logs" / "ptaf-web.log"))
        self.LOG_FILE: Path = Path(log_file)

        # ---------- WAF API connection ----------
        # Base URL of PTAF PRO instance, e.g. "https://ptaf.example.com"
        self.AF_URL: str = os.getenv("AF_URL", "").rstrip("/")
        # API path prefix, usually "/api/ptaf/v4"
        self.API_PATH: str = os.getenv("API_PATH", "/api/ptaf/v4").rstrip("/")

        # SSL verification: "true"/"false" or path to CA/cert file
        verify_ssl_env = os.getenv("VERIFY_SSL", "true")
        lower = verify_ssl_env.strip().lower()
        if lower in {"true", "1", "yes", "on"}:
            self.VERIFY_SSL = True
        elif lower in {"false", "0", "no", "off"}:
            self.VERIFY_SSL = False
        else:
            # treat as path
            self.VERIFY_SSL = verify_ssl_env

        # Request timeout in seconds
        self.REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "30"))

        # ---------- Auth credentials ----------
        # Static API token (if present, username/password are ignored)
        self.API_TOKEN: str = _read_secret("API_TOKEN", "API_TOKEN_FILE")

        # Credentials for JWT-based auth
        self.API_LOGIN: str = _read_secret("API_LOGIN", "API_LOGIN_FILE")
        self.API_PASSWORD: str = _read_secret("API_PASSWORD", "API_PASSWORD_FILE")

        # ---------- Snapshot / tenants endpoints ----------
        # These match PTAF PRO defaults but can be overridden via env if needed
        self.TENANTS_ENDPOINT: str = os.getenv(
            "TENANTS_ENDPOINT", f"{self.API_PATH}/auth/account/tenants"
        )

        # Global snapshot endpoint (import/export full config of *current* tenant)
        self.SNAPSHOT_ENDPOINT: str = os.getenv(
            "SNAPSHOT_ENDPOINT", f"{self.API_PATH}/config/snapshot"
        )

        # Directory where JSON snapshots of tenants are stored
        self.SNAPSHOTS_DIR: Path = Path(
            os.getenv("SNAPSHOTS_DIR", str(self.BASE_DIR / "snapshots"))
        ).resolve()

        # Ensure directories exist for local runs (in Docker volumes will be mounted)
        self.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def auth_method(self) -> str:
        """
        Returns which auth method is configured:
          - "token"    — static API_TOKEN
          - "password" — username/password (JWT)
        Raises if nothing is configured.
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
