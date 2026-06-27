from __future__ import annotations

import ipaddress
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

import httpx
from loguru import logger

from .auth import TokenManager, TenantAuth
from .config import config
from .tenants import fetch_tenants
from .snapshots import _slugify


def _extract_filename_from_cd(content_disposition: str) -> str | None:
    """
    Извлекает имя файла из заголовка Content-Disposition.
    """
    match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition)
    if match:
        return unquote(match.group(1))
    match = re.search(r'filename="([^"]+)"', content_disposition)
    if not match:
        match = re.search(r"filename=([^;]+)", content_disposition)
    if match:
        return match.group(1).strip('"')
    return None


async def export_global_lists_for_tenant(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant: Dict[str, Any],
) -> List[Path]:
    """
    Экспорт глобальных списков тенанта во временную директорию.
    """
    tenant_id = str(tenant.get("id"))
    name = _slugify(str(tenant.get("name") or tenant.get("displayName") or tenant_id))
    subdir = config.GLOBAL_LISTS_DIR / f"{name}_{tenant_id}"
    subdir.mkdir(parents=True, exist_ok=True)

    url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}"
    logger.info(f"[tenant={tenant_id}] Exporting global lists from {url}")

    auth = TenantAuth(tm, tenant_id=tenant_id)
    try:
        r = await client.get(url, auth=auth)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"[tenant={tenant_id}] Failed to export global lists: {e}")
        return []

    items = _normalize_items(r.json())
    created: List[Path] = []

    for gl in items:
        gl_id = gl.get("id") or gl.get("name") or "global_list"

        fname_json = subdir / f"{_slugify(str(gl_id))}.globallist.json"
        fname_json.write_text(
            json.dumps(gl, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        created.append(fname_json)

        base_endpoint = config.GLOBAL_LISTS_ENDPOINT.rstrip('/')
        file_url = f"{config.AF_URL}{base_endpoint}/{gl_id}/file"
        logger.debug(f"[tenant={tenant_id}] Fetching global list file from {file_url}")
        try:
            resp_file = await client.get(file_url, auth=auth)
            resp_file.raise_for_status()
        except Exception as e:
            logger.error(f"[tenant={tenant_id}] Failed to fetch file for list {gl_id}: {e}")
            continue

        cd_header = resp_file.headers.get("content-disposition")
        filename = None
        if cd_header:
            filename = _extract_filename_from_cd(cd_header)
        if not filename:
            filename = f"{_slugify(str(gl_id))}.txt"
        filename = filename.replace("/", "_")
        file_path = subdir / filename

        file_path.write_bytes(resp_file.content)
        logger.debug(f"[tenant={tenant_id}] Saved global list file to {file_path}")
        created.append(file_path)

        logger.success(f"[tenant={tenant_id}] Exported global list {gl_id} (config + file)")

    logger.success(f"[tenant={tenant_id}] Exported {len(created)} objects to {subdir}")
    return created


async def export_global_lists_for_all_tenants(tm: TokenManager) -> List[Path]:
    """Экспорт глобальных списков для всех тенантов."""
    created: List[Path] = []
    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        tenants = await fetch_tenants(client, tm)
        if not tenants:
            logger.warning("No tenants returned by API (global lists export)")
            return []

        for tenant in tenants:
            files = await export_global_lists_for_tenant(client, tm, tenant)
            created.extend(files)

    return created


def _normalize_items(data: Any) -> List[Dict[str, Any]]:
    """Нормализация ответа API."""
    if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
        return data["items"]
    if isinstance(data, list):
        return data
    raise RuntimeError(f"Unsupported list response type: {type(data)}")


async def fetch_global_lists(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
) -> List[Dict[str, Any]]:
    """Получить список глобальных списков."""
    url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}"
    auth = TenantAuth(tm, tenant_id=tenant_id)
    r = await client.get(url, auth=auth)
    r.raise_for_status()
    return _normalize_items(r.json())


async def add_items_to_global_list(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    list_id: str,
    items: List[str],
    ttl: int = 1440,
) -> Dict[str, Any]:
    """Добавить IP-адреса в глобальный список."""
    url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/add_items"
    auth = TenantAuth(tm, tenant_id=tenant_id)
    payload = {
        "global_lists": [list_id],
        "items": items,
        "ttl": ttl,
    }
    r = await client.post(url, json=payload, auth=auth)
    r.raise_for_status()
    return r.json()


async def remove_items_from_global_list(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    list_id: str,
    items: List[str],
) -> Dict[str, Any]:
    """Удалить IP-адреса из глобального списка."""
    url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/remove_items"
    auth = TenantAuth(tm, tenant_id=tenant_id)
    payload = {
        "global_lists": [list_id],
        "items": items,
    }
    r = await client.post(url, json=payload, auth=auth)
    r.raise_for_status()
    return r.json()


async def download_static_list(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    list_id: str,
) -> Tuple[str, Dict[str, Any]]:
    """
    Скачать содержимое статического глобального списка.
    Возвращает (content_text, list_metadata).
    """
    auth = TenantAuth(tm, tenant_id=tenant_id)
    file_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{list_id}/file"
    logger.debug(f"[tenant={tenant_id}] Downloading static list {list_id} from {file_url}")
    
    resp = await client.get(file_url, auth=auth)
    resp.raise_for_status()
    
    metadata_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{list_id}"
    meta_resp = await client.get(metadata_url, auth=auth)
    meta_resp.raise_for_status()
    
    return resp.text, meta_resp.json()


async def upload_static_list(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    list_id: str,
    content: str,
    name: str,
    description: str = "",
) -> Dict[str, Any]:
    """
    Загрузить содержимое статического глобального списка.
    Использует multipart/form-data для загрузки файла.
    """
    import io
    auth = TenantAuth(tm, tenant_id=tenant_id)
    url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{list_id}"
    
    files = {
        "name": (None, name),
        "description": (None, description),
        "file": ("global_list.txt", content.encode("utf-8"), "text/plain"),
    }
    
    logger.debug(f"[tenant={tenant_id}] Uploading static list {list_id} to {url}")
    r = await client.patch(url, files=files, auth=auth)
    r.raise_for_status()
    return r.json()


def parse_static_list_content(content: str) -> List[Dict[str, Any]]:
    """
    Парсит содержимое статического списка.
    Возвращает список записей с информацией: type (comment/entry), value, original_line.
    """
    entries = []
    for line in content.splitlines():
        original_line = line
        stripped = line.strip()
        
        if not stripped or stripped.startswith("#"):
            entries.append({
                "type": "comment",
                "value": stripped,
                "original_line": original_line,
            })
        else:
            parts = stripped.split()
            ip_or_subnet = parts[0]
            ttl_or_note = parts[1] if len(parts) > 1 else None
            entries.append({
                "type": "entry",
                "value": ip_or_subnet,
                "ttl": ttl_or_note,
                "original_line": original_line,
            })
    
    return entries


def add_ip_to_static_list_content(
    content: str,
    new_ips: List[str],
) -> Tuple[str, List[str]]:
    """
    Добавить IP-адреса в содержимое статического списка.
    Сохраняет комментарии и существующие записи.
    Возвращает (новый_content, список уже существующих IP).
    """
    entries = parse_static_list_content(content)
    existing_values = {e["value"] for e in entries if e["type"] == "entry"}
    
    already_exist = []
    new_entries = []
    
    for ip in new_ips:
        if ip in existing_values:
            already_exist.append(ip)
        else:
            new_entries.append({"type": "entry", "value": ip, "ttl": None, "original_line": ip})
    
    result_lines = []
    for e in entries:
        result_lines.append(e["original_line"])
    
    for e in new_entries:
        result_lines.append(e["value"])
    
    return "\n".join(result_lines) + "\n", already_exist


def remove_ip_from_static_list_content(
    content: str,
    ips_to_remove: List[str],
) -> Tuple[str, List[str], List[str]]:
    """
    Удалить IP-адреса из содержимого статического списка.
    Сохраняет комментарии и существующие записи.
    Возвращает (новый_content, удалённые IP, IP которые не найдены).
    
    Также проверяет, является ли IP частью подсети - если да, не удаляет.
    """
    entries = parse_static_list_content(content)
    
    removed = []
    not_found = []
    
    ips_to_remove_set = set(ips_to_remove)
    
    result_entries = []
    for e in entries:
        if e["type"] == "entry":
            entry_ip = e["value"]
            if entry_ip in ips_to_remove_set:
                removed.append(entry_ip)
                continue
            if _is_ip_in_subnets(entry_ip, ips_to_remove_set):
                logger.info(f"IP {entry_ip} is part of a subnet, not removing")
                not_found.append(entry_ip)
                continue
        result_entries.append(e)
    
    for ip in ips_to_remove:
        if ip not in removed and ip not in not_found:
            not_found.append(ip)
    
    result_lines = [e["original_line"] for e in result_entries]
    return "\n".join(result_lines) + "\n" if result_lines else "", removed, not_found


def _is_ip_in_subnets(ip_str: str, subnet_strs: set) -> bool:
    """
    Проверяет, является ли IP частью какой-либо подсети из набора.
    """
    try:
        ip_obj = ipaddress.ip_address(ip_str.split("/")[0])
        
        for subnet_str in subnet_strs:
            try:
                if "/" in subnet_str:
                    subnet_obj = ipaddress.ip_network(subnet_str, strict=False)
                    if ip_obj in subnet_obj:
                        return True
            except ValueError:
                continue
    except ValueError:
        pass
    
    return False


def is_ip_in_subnet(ip_to_check: str, content: str) -> Tuple[bool, List[str]]:
    """
    Проверяет, является ли IP частью какой-либо подсети в списке.
    Возвращает (is_in_subnet, список подсетей содержащих IP).
    """
    try:
        ip_obj = ipaddress.ip_address(ip_to_check.split("/")[0])
    except ValueError:
        return False, []
    
    containing_subnets = []
    entries = parse_static_list_content(content)
    
    for e in entries:
        if e["type"] == "entry" and "/" in e["value"]:
            try:
                subnet_obj = ipaddress.ip_network(e["value"], strict=False)
                if ip_obj in subnet_obj:
                    containing_subnets.append(e["value"])
            except ValueError:
                continue
    
    return len(containing_subnets) > 0, containing_subnets


async def apply_global_lists(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Применяет изменения глобальных списков для тенанта.
    POST /global_lists/apply
    """
    url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/apply"
    auth = TenantAuth(tm, tenant_id=tenant_id)
    logger.debug(f"[tenant={tenant_id}] Applying global lists at {url}")
    r = await client.post(url, auth=auth)
    r.raise_for_status()
    return {"status": "OK", "message": "Global lists applied successfully"}


async def create_global_list_for_tenant(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    name: str,
    list_type: str,
    description: str = "",
    file_content: str = None,
    force_overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Создать новый глобальный список для конкретного тенанта.
    Для STATIC - требует file_content.
    Для DYNAMIC - file_content опционален.
    
    Если force_overwrite=True и список существует, он будет перезаписан.
    """
    import io
    auth = TenantAuth(tm, tenant_id=tenant_id)
    url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}"
    
    existing_list = None
    try:
        lists_resp = await client.get(url, auth=auth)
        lists_resp.raise_for_status()
        lists_data = _normalize_items(lists_resp.json())
        for gl in lists_data:
            if gl.get("name") == name:
                existing_list = gl
                break
    except Exception as e:
        logger.warning(f"[tenant={tenant_id}] Failed to check for existing list: {e}")
    
    if existing_list:
        if not force_overwrite:
            logger.warning(f"[tenant={tenant_id}] Global list '{name}' already exists (id={existing_list.get('id')}). Use force_overwrite=True to overwrite.")
            return {
                "status": "exists",
                "list_id": existing_list.get("id"),
                "message": f"Global list '{name}' already exists. Set force_overwrite=true to overwrite.",
            }
        
        logger.info(f"[tenant={tenant_id}] Overwriting existing global list '{name}' (id={existing_list.get('id')})")
        existing_list_id = existing_list.get("id")
        
        if list_type == "STATIC" and file_content:
            files = {
                "name": (None, name),
                "type": (None, list_type),
                "file": ("global_list.txt", file_content.encode("utf-8"), "text/plain"),
            }
            if description:
                files["description"] = (None, description)
            
            logger.debug(f"[tenant={tenant_id}] Overwriting STATIC global list '{name}' at {url}/{existing_list_id}")
            r = await client.patch(f"{url}/{existing_list_id}", files=files, auth=auth)
        else:
            payload = {
                "name": name,
                "type": list_type,
            }
            if description:
                payload["description"] = description
            
            logger.debug(f"[tenant={tenant_id}] Overwriting {list_type} global list '{name}' at {url}/{existing_list_id}")
            r = await client.patch(f"{url}/{existing_list_id}", json=payload, auth=auth)
        
        r.raise_for_status()
        return {
            "status": "overwritten",
            "list_id": existing_list_id,
            "data": r.json(),
        }
    
    logger.info(f"[tenant={tenant_id}] Creating new global list '{name}'")
    if list_type == "STATIC" and file_content:
        files = {
            "name": (None, name),
            "type": (None, list_type),
            "file": ("global_list.txt", file_content.encode("utf-8"), "text/plain"),
        }
        if description:
            files["description"] = (None, description)
        
        logger.debug(f"[tenant={tenant_id}] Creating STATIC global list '{name}' at {url}")
        r = await client.post(url, files=files, auth=auth)
    else:
        payload = {
            "name": name,
            "type": list_type,
        }
        if description:
            payload["description"] = description
        
        logger.debug(f"[tenant={tenant_id}] Creating {list_type} global list '{name}' at {url}")
        r = await client.post(url, json=payload, auth=auth)
    
    r.raise_for_status()
    return {
        "status": "created",
        "data": r.json(),
    }


async def create_global_list(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    name: str,
    list_type: str,
    description: str = "",
    file_content: str = None,
    force_overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Создать глобальный список для одного или всех тенантов.
    
    Если tenant_id == "__all__", список будет создан для всех тенантов.
    Если force_overwrite=True, существующие списки будут перезаписаны.
    """
    if tenant_id == "__all__":
        tenants = await fetch_tenants(client, tm)
        if not tenants:
            return {"status": "error", "message": "No tenants found"}
        
        results = []
        for tenant in tenants:
            tid = str(tenant.get("id"))
            try:
                result = await create_global_list_for_tenant(
                    client, tm, tid, name, list_type, description, file_content, force_overwrite
                )
                results.append({
                    "tenant_id": tid,
                    "tenant_name": tenant.get("name") or tenant.get("displayName") or tid,
                    **result,
                })
            except Exception as e:
                results.append({
                    "tenant_id": tid,
                    "tenant_name": tenant.get("name") or tenant.get("displayName") or tid,
                    "status": "error",
                    "error": str(e),
                })
        
        success_count = len([r for r in results if r.get("status") in ("created", "overwritten", "exists")])
        return {
            "results": results,
            "summary": {
                "total": len(results),
                "success": success_count,
                "failed": len(results) - success_count,
            },
        }
    else:
        return await create_global_list_for_tenant(
            client, tm, tenant_id, name, list_type, description, file_content, force_overwrite
        )
