from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

import httpx
from loguru import logger

from .auth import TokenManager, TenantAuth
from .config import config
from .tenants import fetch_tenants


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "tenant"


def _snapshot_filename(tenant: Dict[str, Any]) -> Path:
    name = _slugify(
        str(tenant.get("name") or tenant.get("displayName") or tenant.get("id"))
    )
    tenant_id = tenant.get("id", "unknown")
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fname = f"{ts}_{name}_{tenant_id}.snapshot.json"
    return config.SNAPSHOTS_DIR / fname


def cleanup_old_snapshots() -> int:
    """
    Удаляет снапшоты старше SNAPSHOT_RETENTION_DAYS, если параметр задан.

    Возвращает количество удалённых файлов.
    """

    retention_days = config.SNAPSHOT_RETENTION_DAYS
    if not retention_days:
        return 0

    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    removed = 0

    for path in config.SNAPSHOTS_DIR.glob("*.snapshot.json"):
        try:
            mtime = datetime.utcfromtimestamp(path.stat().st_mtime)
        except OSError:
            continue

        if mtime < cutoff:
            try:
                path.unlink()
                removed += 1
            except OSError:
                logger.warning(f"Failed to delete old snapshot: {path}")

    if removed:
        logger.info(
            f"Removed {removed} snapshots older than {retention_days} days"
        )

    return removed


def _tenant_id_from_snapshot_path(path: Path) -> Optional[str]:
    """
    Extract tenant ID from snapshot filename.

    Filenames follow pattern: ``{ts}_{name}_{tenant_id}.snapshot.json``.
    """

    parts = path.stem.rsplit("_", 1)
    if len(parts) < 2:
        return None
    tenant_part = parts[-1]
    if tenant_part.endswith(".snapshot"):
        tenant_part = tenant_part[: -len(".snapshot")]
    return tenant_part


def latest_snapshot_per_tenant() -> Dict[str, str]:
    """
    Returns mapping tenant_id -> latest snapshot mtime (ISO string, UTC).
    """

    latest: Dict[str, datetime] = {}

    for path in config.SNAPSHOTS_DIR.glob("*.snapshot.json"):
        tenant_id = _tenant_id_from_snapshot_path(path)
        if not tenant_id:
            continue

        try:
            mtime = datetime.utcfromtimestamp(path.stat().st_mtime)
        except OSError:
            continue

        current = latest.get(tenant_id)
        if not current or mtime > current:
            latest[tenant_id] = mtime

    return {
        tid: dt.replace(microsecond=0).isoformat() + "Z" for tid, dt in latest.items()
    }


def _snapshot_metadata(path: Path) -> Dict[str, Any]:
    """
    Формирует короткое описание файла снапшота для UI.
    """

    try:
        mtime = datetime.utcfromtimestamp(path.stat().st_mtime)
        size = path.stat().st_size
    except OSError:
        mtime = None
        size = 0

    base_name = path.name
    if base_name.endswith(".snapshot.json"):
        base_name = base_name[: -len(".json")]

    parts = base_name.split("_")
    ts = parts[0] if parts else ""
    tenant_label = " ".join(parts[1:-1]).strip() if len(parts) > 2 else None

    return {
        "filename": path.name,
        "tenant_id": _tenant_id_from_snapshot_path(path),
        "tenant_label": tenant_label or None,
        "timestamp": ts or None,
        "modified_at": mtime.replace(microsecond=0).isoformat() + "Z"
        if mtime
        else None,
        "size_bytes": size,
    }


def list_local_snapshots() -> List[Dict[str, Any]]:
    """
    Возвращает список локальных файлов снапшотов из каталога данных.
    API вызовы не используются — только чтение файлов.
    """

    snapshots: List[Dict[str, Any]] = []
    for path in sorted(
        config.SNAPSHOTS_DIR.glob("*.snapshot.json"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    ):
        if not path.is_file():
            continue
        snapshots.append(_snapshot_metadata(path))

    return snapshots


def load_snapshot_file(filename: str) -> Dict[str, Any]:
    """
    Читает содержимое файла снапшота по имени файла.

    Имя должно оканчиваться на `.snapshot.json`, путь traversal запрещён.
    """

    if "/" in filename or ".." in Path(filename).parts:
        raise ValueError("Invalid snapshot filename")

    if not filename.endswith(".snapshot.json"):
        raise ValueError("Snapshot filename must end with .snapshot.json")

    path = config.SNAPSHOTS_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(filename)

    return json.loads(path.read_text(encoding="utf-8"))


async def export_snapshot_for_tenant(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant: Dict[str, Any],
) -> Optional[Path]:
    """
    Экспорт полного снапшота конфигурации для ОДНОГО тенанта.

    В PTAF PRO используется глобальный эндпоинт /config/snapshot,
    а конкретный тенант выбирается через JWT (TenantAuth).
    """
    tenant_id = str(tenant.get("id"))
    if not tenant_id:
        logger.error(f"Tenant object has no 'id': {tenant}")
        return None

    fname = _snapshot_filename(tenant)
    url = f"{config.AF_URL}{config.SNAPSHOT_ENDPOINT}"
    logger.info(f"[tenant={tenant_id}] Exporting snapshot from {url}")

    auth = TenantAuth(tm, tenant_id=tenant_id)
    r = await client.get(url, auth=auth)
    if r.status_code != 200:
        logger.error(
            f"[tenant={tenant_id}] Snapshot export failed: "
            f"{r.status_code} {r.text}"
        )
        return None

    data = r.json()
    fname.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.success(f"[tenant={tenant_id}] Snapshot written to {fname}")
    return fname


async def export_all_tenant_snapshots(tm: TokenManager) -> List[Path]:
    """
    Стадия инициализации:

    1. Авторизация в API.
    2. Получение списка всех доступных тенантов.
    3. Экспорт полного снапшота каждого тенанта в отдельный JSON-файл
       в директорию config.SNAPSHOTS_DIR.

    Возвращает список созданных файлов.
    """
    created_files: List[Path] = []

    removed = cleanup_old_snapshots()
    if removed:
        logger.info(f"Cleanup complete: {removed} old snapshots removed")

    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        # 1. Проверяем, что можем авторизоваться
        token = await tm.ensure_base_token(client)
        if not token:
            raise RuntimeError(
                "Unable to obtain base access token (check credentials)"
            )

        # 2. Тенанты
        tenants = await fetch_tenants(client, tm)
        if not tenants:
            logger.warning("No tenants returned by API")
            return []

        logger.info(f"Exporting snapshots for {len(tenants)} tenants")

        # 3. Экспорт по каждому тенанту
        for tenant in tenants:
            path = await export_snapshot_for_tenant(client, tm, tenant)
            if path:
                created_files.append(path)

    logger.info(f"Total snapshots written: {len(created_files)}")
    return created_files
