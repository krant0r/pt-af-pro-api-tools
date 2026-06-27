from __future__ import annotations

import asyncio
import copy
import io
import json
import tarfile
from datetime import datetime
from typing import Any, Dict, List, Tuple

import httpx
from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from loguru import logger

from .auth import TenantAuth, TokenManager, AuthenticationError
from .config import config
from .global_lists import (
    export_global_lists_for_tenant,
    export_global_lists_for_all_tenants,
    _normalize_items,
    download_static_list,
    upload_static_list,
    add_ip_to_static_list_content,
    remove_ip_from_static_list_content,
    is_ip_in_subnet,
    apply_global_lists,
    create_global_list,
)
from .rules_actions import (
    export_actions_for_tenant,
    export_rules_for_tenant,
    import_action_payload,
    import_rule_payload,
    import_rule_from_snapshot,
    list_local_exports,
    load_local_payload,
)
from .snapshots import (
    export_all_tenant_snapshots,
    export_snapshot_for_tenant,
    get_latest_snapshot_path,
    get_applications_from_snapshot,
    get_user_rules_from_snapshot,
    fetch_all_snapshots,
    get_snapshot_cache,
    collect_snapshot_summary_from_cache,
)
from .tenants import fetch_tenants
from .web_utils import (
    fetch_tenants_with_snapshots,
    find_tenant,
    collect_snapshot_summary,
    settings_payload,
)
from .web_ui import INDEX_HTML

# Глобальный менеджер токенов – создаётся сразу, не может быть None
token_manager = TokenManager()

router = APIRouter()


# ---------- Вспомогательные функции для эндпоинтов ----------
async def _fetch_global_lists(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
) -> List[Dict[str, Any]]:
    """Получить список глобальных списков для тенанта."""
    url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}"
    auth = TenantAuth(tm, tenant_id=tenant_id)
    try:
        r = await client.get(url, auth=auth)
        r.raise_for_status()
        data = r.json()
        items = _normalize_items(data)
        logger.debug(f"Fetched {len(items)} global lists for tenant {tenant_id}")
        for item in items:
            logger.debug(f"  List: id={item.get('id')}, name={item.get('name')}, type={item.get('type')}")
        return items
    except Exception as e:
        logger.error(f"Error fetching global lists for tenant {tenant_id}: {type(e).__name__}: {e}")
        raise


async def _get_list_type(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    list_id: str,
) -> str:
    """Получить тип глобального списка (STATIC или DYNAMIC)."""
    url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{list_id}"
    auth = TenantAuth(tm, tenant_id=tenant_id)
    try:
        r = await client.get(url, auth=auth)
        r.raise_for_status()
        data = r.json()
        list_type = data.get("type", "DYNAMIC")
        logger.debug(f"[tenant={tenant_id}] List {list_id} type: {list_type}")
        return list_type
    except Exception as e:
        logger.error(f"Error fetching list type for tenant {tenant_id}, list {list_id}: {type(e).__name__}: {e}")
        return "DYNAMIC"


async def _add_items_to_global_list(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    list_id: str,
    items: list,
    ttl: int = 1440,
) -> Dict[str, Any]:
    """Добавить IP в глобальный список (автоматически определяет тип списка)."""
    list_type = await _get_list_type(client, tm, tenant_id, list_id)
    
    if list_type == "STATIC":
        auth = TenantAuth(tm, tenant_id=tenant_id)
        content, metadata = await download_static_list(client, tm, tenant_id, list_id)
        name = metadata.get("name", "global_list")
        description = metadata.get("description", "")
        
        new_content, already_exist = add_ip_to_static_list_content(content, items)
        
        if already_exist:
            logger.info(f"[tenant={tenant_id}] IPs already exist in static list: {already_exist}")
        
        if new_content == content:
            return {"status": "OK", "message": "All IPs already exist", "already_exist": already_exist}
        
        await upload_static_list(client, tm, tenant_id, list_id, new_content, name, description)
        await apply_global_lists(client, tm, tenant_id)
        
        return {
            "status": "OK",
            "added": len(items) - len(already_exist),
            "already_exist": already_exist,
        }
    else:
        url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/add_items"
        auth = TenantAuth(tm, tenant_id=tenant_id)
        payload = {"global_lists": [list_id], "items": items, "ttl": ttl}
        r = await client.post(url, json=payload, auth=auth)
        r.raise_for_status()
        return r.json()


async def _remove_items_from_global_list(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    list_id: str,
    items: list,
) -> Dict[str, Any]:
    """Удалить IP из глобального списка (автоматически определяет тип списка)."""
    list_type = await _get_list_type(client, tm, tenant_id, list_id)
    
    if list_type == "STATIC":
        auth = TenantAuth(tm, tenant_id=tenant_id)
        content, metadata = await download_static_list(client, tm, tenant_id, list_id)
        name = metadata.get("name", "global_list")
        description = metadata.get("description", "")
        
        new_content, removed, not_found = remove_ip_from_static_list_content(content, items)
        
        if not_found:
            logger.info(f"[tenant={tenant_id}] IPs not found in static list: {not_found}")
        
        if not removed:
            return {"status": "OK", "message": "No IPs removed", "not_found": not_found}
        
        await upload_static_list(client, tm, tenant_id, list_id, new_content, name, description)
        await apply_global_lists(client, tm, tenant_id)
        
        return {
            "status": "OK",
            "removed": removed,
            "not_found": not_found,
        }
    else:
        url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/remove_items"
        auth = TenantAuth(tm, tenant_id=tenant_id)
        payload = {"global_lists": [list_id], "items": items}
        r = await client.post(url, json=payload, auth=auth)
        r.raise_for_status()
        return r.json()


async def _get_tenants_with_global_lists(
    client: httpx.AsyncClient,
    tm: TokenManager,
    list_name: str = "Aggregation blacklist",
) -> List[Dict[str, Any]]:
    """
    Получает список тенантов и для каждого находит глобальный список с указанным именем.
    Возвращает: [{tenant_id, tenant_name, list_id, list_name, list_type}, ...]
    """
    tenants = await fetch_tenants_with_snapshots()
    result = []
    
    for tenant in tenants:
        tenant_id = str(tenant["id"])
        tenant_name = tenant.get("name") or tenant.get("displayName") or tenant_id
        
        try:
            lists = await _fetch_global_lists(client, tm, tenant_id)
            
            # Ищем список с нужным именем
            target_list = None
            for gl in lists:
                gl_name = gl.get("name", "").lower()
                if list_name.lower() in gl_name or gl_name == list_name.lower():
                    target_list = gl
                    break
            
            if target_list:
                result.append({
                    "tenant_id": tenant_id,
                    "tenant_name": tenant_name,
                    "list_id": target_list.get("id"),
                    "list_name": target_list.get("name"),
                    "list_type": target_list.get("type", "DYNAMIC"),
                })
            else:
                logger.warning(f"Global list '{list_name}' not found for tenant {tenant_name} ({tenant_id})")
                
        except Exception as e:
            logger.error(f"Error fetching global lists for tenant {tenant_id}: {e}")
    
    return result


# ---------- Эндпоинты ----------
@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/api/settings")
async def api_get_settings():
    return settings_payload()


@router.post("/api/settings")
async def api_save_settings(request: Request):
    payload = await request.json()
    updates = {}
    mapping = {
        "theme": "THEME",
        "language": "LANGUAGE",
        "af_url": "AF_URL",
        "api_login": "API_LOGIN",
        "api_password": "API_PASSWORD",
        "verify_ssl": "VERIFY_SSL",
        "ldap_auth": "LDAP_AUTH",
        "snapshot_retention_days": "SNAPSHOT_RETENTION_DAYS",
    }
    for key, target in mapping.items():
        if key in payload:
            updates[target] = payload.get(key)
    if updates:
        config.save_settings(updates)
    return settings_payload()


@router.post("/api/init/snapshots")
async def init_snapshots():
    """Получить снапшоты всех тенантов и сохранить в RAM кэш."""
    snapshots, errors = await fetch_all_snapshots(token_manager)
    return JSONResponse(
        {
            "snapshots_cached": len(snapshots),
            "tenant_ids": list(snapshots.keys()),
            "errors": errors,
        }
    )


@router.get("/api/backup")
async def create_backup():
    """
    Создать полный backup всех снапшотов, правил, действий и глобальных списков в виде tar.gz.
    Данные берутся из RAM кэша и временных директорий.
    """
    import tempfile
    import os
    import aiofiles
    
    await fetch_all_snapshots(token_manager)
    
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        tenants_list = await fetch_tenants(client, token_manager)
        if not tenants_list:
            return JSONResponse({"error": "No tenants found"}, status_code=404)
        
        tenant_name_map = {
            str(t.get("id") or ""): t.get("name") or t.get("displayName") or "unnamed"
            for t in tenants_list
        }
        
        for tenant in tenants_list:
            await export_rules_for_tenant(client, token_manager, tenant)
            await export_actions_for_tenant(client, token_manager, tenant)
            await export_global_lists_for_tenant(client, token_manager, tenant)
    
    timestamp = datetime.utcnow().strftime("%Y.%m.%d_%H.%M.%S")
    
    def sanitize_name(name: str) -> str:
        if not name:
            return "unnamed"
        return "".join(c if c.isalnum() or c in " -_.()" else "_" for c in name)
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
    temp_path = temp_file.name
    temp_file.close()
    
    with tarfile.open(temp_path, mode="w:gz") as tar:
        from .snapshots import get_snapshot_cache
        cache = get_snapshot_cache()
        for tenant_id, data in cache.items():
            tenant_name = tenant_name_map.get(tenant_id, "unnamed")
            json_data = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            safe_name = sanitize_name(tenant_name)
            info = tarfile.TarInfo(name=f"snapshots/{tenant_id}.snapshot.{safe_name}.json")
            info.size = len(json_data)
            tar.addfile(info, io.BytesIO(json_data))
        
        if config.RULES_DIR.exists():
            for subdir in config.RULES_DIR.iterdir():
                if subdir.is_dir():
                    for file in subdir.glob("*.rule.json"):
                        try:
                            data = json.loads(file.read_text(encoding="utf-8"))
                            obj_name = sanitize_name(data.get("name", "unnamed"))
                        except Exception:
                            obj_name = "unnamed"
                        base_name = file.stem
                        arcname = f"rules/{subdir.name}/{base_name}.{obj_name}.json"
                        tar.add(file, arcname=arcname)
        
        if config.ACTIONS_DIR.exists():
            for subdir in config.ACTIONS_DIR.iterdir():
                if subdir.is_dir():
                    for file in subdir.glob("*.action.json"):
                        try:
                            data = json.loads(file.read_text(encoding="utf-8"))
                            obj_name = sanitize_name(data.get("name", "unnamed"))
                        except Exception:
                            obj_name = "unnamed"
                        base_name = file.stem
                        arcname = f"actions/{subdir.name}/{base_name}.{obj_name}.json"
                        tar.add(file, arcname=arcname)
        
        if config.GLOBAL_LISTS_DIR.exists():
            for subdir in config.GLOBAL_LISTS_DIR.iterdir():
                if subdir.is_dir():
                    for file in subdir.glob("*"):
                        if file.is_file():
                            if file.suffix.lower() == ".txt":
                                arcname = f"global_lists/{subdir.name}/{file.name}"
                                tar.add(file, arcname=arcname)
                            else:
                                try:
                                    data = json.loads(file.read_text(encoding="utf-8"))
                                    obj_name = sanitize_name(data.get("name", "unnamed"))
                                except Exception:
                                    obj_name = "unnamed"
                                base_name = file.stem
                                arcname = f"global_lists/{subdir.name}/{base_name}.{obj_name}.json"
                                tar.add(file, arcname=arcname)
    
    filename = f"{timestamp}.ptaf_backup.tar.gz"
    
    async def iter_file():
        try:
            async with aiofiles.open(temp_path, mode="rb") as f:
                while chunk := await f.read(65536):
                    yield chunk
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
    
    return StreamingResponse(
        iter_file(),
        media_type="application/x-gtar",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/api/snapshots/summary")
async def api_snapshot_summary():
    """Вернуть summary из RAM кэша. Если кэш пуст, попробовать прочитать из файлов."""
    from .snapshots import get_snapshot_cache
    from .tenants import fetch_tenants
    import httpx
    
    cache = get_snapshot_cache()
    
    # Получаем маппинг tenant_id -> tenant_name для подстановки имен
    tenant_name_map = {}
    try:
        async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
            tm = TokenManager()
            tenants = await fetch_tenants(client, tm)
            tenant_name_map = {
                str(t.get("id") or ""): t.get("name") or t.get("displayName") or str(t.get("id") or "")
                for t in tenants
            }
    except Exception as e:
        logger.warning(f"Failed to fetch tenants for name mapping: {e}")
    
    if cache:
        from .snapshots import collect_snapshot_summary_from_cache
        result = collect_snapshot_summary_from_cache()
        # Обновляем имена тенантов в результате, используя маппинг
        for entry in result.get("tenant_hosts", []):
            tenant_id = entry.get("tenant_id")
            if tenant_id and tenant_id in tenant_name_map:
                entry["tenant_name"] = tenant_name_map[tenant_id]
        return result
    else:
        logger.warning("Snapshot cache is empty, falling back to file-based summary")
        from .web_utils import collect_snapshot_summary_from_files
        result = collect_snapshot_summary_from_files()
        # Обновляем имена тенантов в результате, используя маппинг
        for entry in result.get("tenant_hosts", []):
            tenant_id = entry.get("tenant_id")
            if tenant_id and tenant_id in tenant_name_map:
                entry["tenant_name"] = tenant_name_map[tenant_id]
        return result


@router.get("/api/tenants")
async def api_tenants():
    try:
        return await fetch_tenants_with_snapshots()
    except AuthenticationError as e:
        logger.error(f"Authentication error in api_tenants: {e}")
        return JSONResponse({"error": "authentication_failed", "message": str(e)}, status_code=401)
    except Exception as e:
        logger.error(f"Error in api_tenants: {type(e).__name__}: {e}")
        return JSONResponse({"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/auth/check")
async def api_auth_check():
    """Проверяет корректность учётных данных."""
    try:
        tenants = await fetch_tenants_with_snapshots()
        return {"status": "ok", "tenants_count": len(tenants)}
    except AuthenticationError as e:
        logger.error(f"Authentication check failed: {e}")
        return JSONResponse({"error": "authentication_failed", "message": str(e)}, status_code=401)
    except Exception as e:
        logger.error(f"Authentication check error: {type(e).__name__}: {e}")
        return JSONResponse({"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/tenants/{tenant_id}/snapshot")
async def api_snapshot_tenant(tenant_id: str):
    tenant = await find_tenant(tenant_id)
    if not tenant:
        return JSONResponse({"error": f"Tenant {tenant_id} not found"}, status_code=404)
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        path = await export_snapshot_for_tenant(client, token_manager, tenant)
    if not path:
        return JSONResponse({"error": "Snapshot export failed", "file": None}, status_code=200)
    return {"file": str(path)}


@router.post("/api/tenants/{tenant_id}/rules/export")
async def api_export_rules(tenant_id: str):
    tenant = await find_tenant(tenant_id)
    if not tenant:
        return JSONResponse({"error": f"Tenant {tenant_id} not found"}, status_code=404)
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        files = await export_rules_for_tenant(client, token_manager, tenant)
    return {"exported": len(files), "files": [str(p) for p in files]}


@router.post("/api/tenants/{tenant_id}/actions/export")
async def api_export_actions(tenant_id: str):
    tenant = await find_tenant(tenant_id)
    if not tenant:
        return JSONResponse({"error": f"Tenant {tenant_id} not found"}, status_code=404)
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        files = await export_actions_for_tenant(client, token_manager, tenant)
    return {"exported": len(files), "files": [str(p) for p in files]}


@router.post("/api/tenants/{tenant_id}/global_lists/export")
async def api_export_global_lists(tenant_id: str):
    tenant = await find_tenant(tenant_id)
    if not tenant:
        return JSONResponse({"error": f"Tenant {tenant_id} not found"}, status_code=404)
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        files = await export_global_lists_for_tenant(client, token_manager, tenant)
    return {"exported": len(files), "files": [str(p) for p in files]}


@router.post("/api/global_lists/export/all")
async def api_export_global_lists_all():
    files = await export_global_lists_for_all_tenants(token_manager)
    return {"exported": len(files), "files": [str(p) for p in files]}


@router.get("/api/tenants/{tenant_id}/global_lists")
async def api_get_global_lists(tenant_id: str):
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        try:
            lists = await _fetch_global_lists(client, token_manager, tenant_id)
            return lists
        except Exception as e:
            logger.error(f"Failed to fetch global lists: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)
        

async def _apply_global_lists_safe(client: httpx.AsyncClient, tm: TokenManager, tenant_id: str) -> Tuple[bool, str]:
    """
    Безопасно применяет глобальные списки для тенанта.
    Возвращает (success: bool, message: str).
    """
    try:
        await apply_global_lists(client, tm, tenant_id)
        return True, "Global lists applied successfully"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            return False, "No permissions to apply global lists (403 Forbidden)"
        elif e.response.status_code == 404:
            return False, "Global lists endpoint not found (404)"
        else:
            return False, f"HTTP error {e.response.status_code}: {str(e)[:100]}"
    except Exception as e:
        return False, f"Error: {str(e)[:100]}"


@router.post("/api/global_lists/create")
async def api_create_global_list(request: Request):
    """Создать новый глобальный список."""
    try:
        content_type = request.headers.get("Content-Type", "")
        
        if "multipart/form-data" in content_type:
            async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
                form = await request.form()
                tenant_id = form.get("tenant_id")
                name = form.get("name")
                list_type = form.get("type", "DYNAMIC")
                description = form.get("description", "")
                file = form.get("file")
                force_overwrite = form.get("force_overwrite", "false").lower() == "true"
                
                if not tenant_id or not name or not list_type:
                    return JSONResponse({"error": "tenant_id, name, and type are required"}, status_code=400)
                
                file_content = None
                if file and hasattr(file, 'read'):
                    file_content = await file.read()
                    file_content = file_content.decode("utf-8")
                
                result = await create_global_list(
                    client, token_manager, tenant_id,
                    name, list_type, description, file_content, force_overwrite
                )
                
                # Для STATIC списков выполняем apply
                if list_type == "STATIC" and file_content:
                    if tenant_id == "__all__":
                        tenants = await fetch_tenants(client, token_manager)
                        apply_results = {}
                        for tenant in tenants:
                            tid = str(tenant.get("id"))
                            success, msg = await _apply_global_lists_safe(client, token_manager, tid)
                            apply_results[tid] = {"success": success, "message": msg}
                        
                        if isinstance(result, dict) and "results" in result:
                            for r in result["results"]:
                                tid = r.get("tenant_id")
                                if tid in apply_results:
                                    if apply_results[tid]["success"]:
                                        r["apply_status"] = "applied"
                                        r["apply_message"] = apply_results[tid]["message"]
                                    else:
                                        r["apply_status"] = "apply_failed"
                                        r["apply_message"] = apply_results[tid]["message"]
                        result["apply_summary"] = apply_results
                    else:
                        success, msg = await _apply_global_lists_safe(client, token_manager, tenant_id)
                        if isinstance(result, dict):
                            result["apply_status"] = "applied" if success else "apply_failed"
                            result["apply_message"] = msg
                
                return result
        else:
            body = await request.json()
            tenant_id = body.get("tenant_id")
            name = body.get("name")
            list_type = body.get("type", "DYNAMIC")
            description = body.get("description", "")
            file_content = body.get("file_content")
            force_overwrite = body.get("force_overwrite", False)
            
            if not tenant_id or not name or not list_type:
                return JSONResponse({"error": "tenant_id, name, and type are required"}, status_code=400)
            
            async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
                result = await create_global_list(
                    client, token_manager, tenant_id,
                    name, list_type, description, file_content, force_overwrite
                )
                
                # Для STATIC списков с содержимым выполняем apply
                if list_type == "STATIC" and file_content:
                    if tenant_id == "__all__":
                        tenants = await fetch_tenants(client, token_manager)
                        apply_results = {}
                        for tenant in tenants:
                            tid = str(tenant.get("id"))
                            success, msg = await _apply_global_lists_safe(client, token_manager, tid)
                            apply_results[tid] = {"success": success, "message": msg}
                        
                        if isinstance(result, dict) and "results" in result:
                            for r in result["results"]:
                                tid = r.get("tenant_id")
                                if tid in apply_results:
                                    if apply_results[tid]["success"]:
                                        r["apply_status"] = "applied"
                                        r["apply_message"] = apply_results[tid]["message"]
                                    else:
                                        r["apply_status"] = "apply_failed"
                                        r["apply_message"] = apply_results[tid]["message"]
                        result["apply_summary"] = apply_results
                    else:
                        success, msg = await _apply_global_lists_safe(client, token_manager, tenant_id)
                        if isinstance(result, dict):
                            result["apply_status"] = "applied" if success else "apply_failed"
                            result["apply_message"] = msg
                
                return result
                
    except Exception as e:
        logger.error(f"Failed to create global list: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/global_lists/add_item")
async def api_add_item_to_global_list(request: Request):
    body = await request.json()
    tenant_id = body.get("tenant_id")
    list_id = body.get("list_id")
    items = body.get("items", [])
    ttl = body.get("ttl", 1440)
    
    if not items:
        return JSONResponse({"error": "items are required"}, status_code=400)
    
    if ttl < 1 or ttl > 10080:
        return JSONResponse({"error": "ttl must be between 1 and 10080 minutes"}, status_code=400)

    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        # Для всех тенантов - ищем "Aggregation blacklist" в каждом
        if tenant_id == "__all__":
            # Получаем все тенанты с их глобальными списками
            tenants_with_lists = await _get_tenants_with_global_lists(client, token_manager, "Aggregation blacklist")
            results = []
            
            for t in tenants_with_lists:
                tid = t["tenant_id"]
                list_id_for_tenant = t["list_id"]
                try:
                    res = await _add_items_to_global_list(client, token_manager, tid, list_id_for_tenant, items, ttl)
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t["tenant_name"],
                        "list_name": t["list_name"],
                        "list_type": t.get("list_type", "DYNAMIC"),
                        "status": res.get("status", "OK"),
                        "already_exist": res.get("already_exist", []),
                    })
                except Exception as e:
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t["tenant_name"],
                        "error": str(e)
                    })
            
            success_count = len([r for r in results if "error" not in r])
            return {
                "results": results,
                "summary": {
                    "total": len(results),
                    "success": success_count,
                    "failed": len(results) - success_count
                }
            }
        else:
            # Конкретный тенант
            if not tenant_id:
                return JSONResponse({"error": "tenant_id is required"}, status_code=400)
            if not list_id:
                return JSONResponse({"error": "list_id is required for specific tenant"}, status_code=400)
            
            res = await _add_items_to_global_list(client, token_manager, tenant_id, list_id, items, ttl)
            return res


@router.post("/api/global_lists/remove_item")
async def api_remove_item_from_global_list(request: Request):
    body = await request.json()
    tenant_id = body.get("tenant_id")
    list_id = body.get("list_id")
    items = body.get("items", [])
    
    if not items:
        return JSONResponse({"error": "items are required"}, status_code=400)

    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        # Для всех тенантов - ищем "Aggregation blacklist" в каждом
        if tenant_id == "__all__":
            tenants_with_lists = await _get_tenants_with_global_lists(client, token_manager, "Aggregation blacklist")
            results = []
            
            for t in tenants_with_lists:
                tid = t["tenant_id"]
                list_id_for_tenant = t["list_id"]
                try:
                    res = await _remove_items_from_global_list(client, token_manager, tid, list_id_for_tenant, items)
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t["tenant_name"],
                        "list_name": t["list_name"],
                        "list_type": t.get("list_type", "DYNAMIC"),
                        "status": res.get("status", "OK"),
                        "removed": res.get("removed", []),
                        "not_found": res.get("not_found", []),
                    })
                except Exception as e:
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t["tenant_name"],
                        "error": str(e)
                    })
            
            success_count = len([r for r in results if "error" not in r])
            return {
                "results": results,
                "summary": {
                    "total": len(results),
                    "success": success_count,
                    "failed": len(results) - success_count
                }
            }
        else:
            # Конкретный тенант
            if not tenant_id:
                return JSONResponse({"error": "tenant_id is required"}, status_code=400)
            if not list_id:
                return JSONResponse({"error": "list_id is required for specific tenant"}, status_code=400)
            
            try:
                res = await _remove_items_from_global_list(client, token_manager, tenant_id, list_id, items)
                return res
            except Exception as e:
                return {"status": "OK", "message": "Items processed (may not have existed)"}


@router.post("/api/tenants/{tenant_id}/rules/import")
async def api_import_rule(tenant_id: str, file: UploadFile = File(...)):
    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        result = await import_rule_payload(client, token_manager, tenant_id, payload)
    return result


@router.post("/api/tenants/{tenant_id}/actions/import")
async def api_import_action(tenant_id: str, file: UploadFile = File(...)):
    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        result = await import_action_payload(client, token_manager, tenant_id, payload)
    return result


@router.get("/api/local-imports")
async def api_list_local_imports():
    return {
        "rules": list_local_exports(config.RULES_DIR, "rule"),
        "actions": list_local_exports(config.ACTIONS_DIR, "action"),
    }


@router.get("/api/local-imports/rules/{tenant_name}/{rule_name}")
async def api_download_local_rule(tenant_name: str, rule_name: str):
    """Скачать JSON пользовательского правила из локального экспорта."""
    from urllib.parse import unquote
    tenant_name = unquote(tenant_name)
    rule_name = unquote(rule_name)
    try:
        payload = load_local_payload(config.RULES_DIR, tenant_name, f"{rule_name}.rule.json", "rule")
        from fastapi.responses import JSONResponse
        return JSONResponse(payload, headers={"Content-Disposition": f'attachment; filename="{rule_name}.json"'})
    except FileNotFoundError:
        return JSONResponse({"error": "Rule not found"}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.get("/api/local-imports/actions/{tenant_name}/{filename:path}")
async def api_download_local_action(tenant_name: str, filename: str):
    """Скачать JSON действия из локального экспорта."""
    from urllib.parse import unquote
    tenant_name = unquote(tenant_name)
    filename = unquote(filename)
    try:
        payload = load_local_payload(config.ACTIONS_DIR, tenant_name, filename, "action")
        from fastapi.responses import JSONResponse
        return JSONResponse(payload, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except FileNotFoundError:
        return JSONResponse({"error": "Action not found"}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.get("/api/snapshots/user-rules")
async def api_list_user_rules_from_snapshots():
    """Возвращает список tenant_name -> [user_rule_names] из RAM кэша."""
    from .snapshots import get_snapshot_cache, _slugify
    results: List[Dict[str, Any]] = []
    cache = get_snapshot_cache()
    for tenant_id, data in cache.items():
        # Пытаемся получить имя тенанта из meta
        tenant_name = data.get("meta", {}).get("tenant", {}).get("name")
        if not tenant_name:
            # Если нет, используем имя из первого приложения или tenant_id
            applications = data.get("applications", [])
            if applications and applications[0].get("name"):
                tenant_name = applications[0].get("name")
            else:
                tenant_name = tenant_id
        user_rules = data.get("user_rules", [])
        if isinstance(user_rules, list) and user_rules:
            results.append({
                "tenant_name": tenant_name,
                "tenant_id": tenant_id,
                "user_rules": [{"name": rule.get("name", "Unnamed")} for rule in user_rules],
            })
    return results


@router.post("/api/tenants/{tenant_id}/rules/import/from-snapshot")
async def api_import_rule_from_snapshot(tenant_id: str, request: Request):
    """Импорт пользовательского правила из снапшота другого тенанта."""
    payload = await request.json()
    source_tenant = payload.get("source_tenant", "").strip()
    rule_name = payload.get("rule_name", "").strip()
    if not source_tenant or not rule_name:
        return JSONResponse({"error": "source_tenant and rule_name required"}, status_code=400)
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        result = await import_rule_from_snapshot(client, token_manager, tenant_id, source_tenant, rule_name)
    if "error" in result:
        return JSONResponse(result, status_code=400 if "not found" in result["error"].lower() else 500)
    return result


@router.post("/api/tenants/{tenant_id}/rules/import/local")
async def api_import_rule_local(tenant_id: str, request: Request):
    payload = await request.json()
    source_tenant = payload.get("source_tenant", "").strip()
    filename = payload.get("filename", "").strip()
    if not source_tenant or not filename:
        return JSONResponse({"error": "source_tenant and filename required"}, status_code=400)
    try:
        local_payload = load_local_payload(config.RULES_DIR, source_tenant, filename, "rule")
    except FileNotFoundError:
        return JSONResponse({"error": "File not found"}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        result = await import_rule_payload(client, token_manager, tenant_id, local_payload)
    return result


@router.post("/api/tenants/{tenant_id}/actions/import/local")
async def api_import_action_local(tenant_id: str, request: Request):
    payload = await request.json()
    source_tenant = payload.get("source_tenant", "").strip()
    filename = payload.get("filename", "").strip()
    if not source_tenant or not filename:
        return JSONResponse({"error": "source_tenant and filename required"}, status_code=400)
    try:
        local_payload = load_local_payload(config.ACTIONS_DIR, source_tenant, filename, "action")
    except FileNotFoundError:
        return JSONResponse({"error": "File not found"}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        result = await import_action_payload(client, token_manager, tenant_id, local_payload)
    return result


@router.post("/api/tenants/{target_tenant_id}/import_application")
async def api_import_application(target_tenant_id: str, request: Request):
    body = await request.json()
    source_tenant_id = body.get("source_tenant_id")
    application_id = body.get("application_id")
    if not source_tenant_id or not application_id:
        return JSONResponse({"error": "source_tenant_id and application_id required"}, status_code=400)

    source_snapshot_path = get_latest_snapshot_path(source_tenant_id)
    if not source_snapshot_path:
        return JSONResponse({"error": f"No snapshot for source tenant {source_tenant_id}"}, status_code=404)

    try:
        source_data = json.loads(source_snapshot_path.read_text(encoding="utf-8"))
        applications = source_data.get("applications", [])
        selected_app = None
        for app in applications:
            if str(app.get("id")) == str(application_id):
                selected_app = app
                break
        if not selected_app:
            return JSONResponse({"error": f"Application {application_id} not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Read source snapshot error: {e}")
        return JSONResponse({"error": "Failed to read source snapshot"}, status_code=500)

    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        target_auth = TenantAuth(token_manager, tenant_id=target_tenant_id)
        snapshot_url = f"{config.AF_URL}{config.SNAPSHOT_ENDPOINT}"
        try:
            resp = await client.get(snapshot_url, auth=target_auth)
            resp.raise_for_status()
            target_snapshot = resp.json()
        except Exception as e:
            return JSONResponse({"error": f"Failed to fetch target snapshot: {str(e)}"}, status_code=500)

        target_apps = target_snapshot.get("applications", [])
        replaced = False
        for i, app in enumerate(target_apps):
            if str(app.get("id")) == str(application_id):
                target_apps[i] = selected_app
                replaced = True
                break
        if not replaced:
            target_apps.append(selected_app)
        target_snapshot["applications"] = target_apps

        import_url = f"{config.AF_URL}{config.SNAPSHOT_IMPORT_TASKS_ENDPOINT}"
        try:
            import_resp = await client.post(import_url, json=target_snapshot, auth=target_auth)
            if import_resp.status_code != 201:
                return JSONResponse({"error": f"Import task failed: {import_resp.text}"}, status_code=import_resp.status_code)
            task = import_resp.json()
            task_id = task.get("id")
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

        # Ожидание завершения задачи
        status_url = f"{config.AF_URL}{config.SNAPSHOT_IMPORT_TASKS_ENDPOINT}"
        for _ in range(30):
            await asyncio.sleep(2)
            try:
                status_resp = await client.get(status_url, auth=target_auth)
                status_resp.raise_for_status()
                tasks = status_resp.json().get("items", [])
                for t in tasks:
                    if t.get("id") == task_id:
                        status = t.get("status")
                        if status == "SUCCESS":
                            await export_snapshot_for_tenant(client, token_manager, {"id": target_tenant_id})
                            return {"success": True, "task_id": task_id, "status": status}
                        elif status == "FAILED":
                            return JSONResponse({"error": "Import task failed", "task_id": task_id}, status_code=500)
                        break
            except Exception:
                pass
        return JSONResponse({"error": "Import task timeout", "task_id": task_id}, status_code=504)


@router.post("/api/tenants/{target_tenant_id}/merge_application_json")
async def api_merge_application_json(target_tenant_id: str, request: Request):
    body = await request.json()
    source_tenant_id = body.get("source_tenant_id")
    application_id = body.get("application_id")
    if not source_tenant_id or not application_id:
        return JSONResponse({"error": "source_tenant_id and application_id required"}, status_code=400)

    source_snapshot_path = get_latest_snapshot_path(source_tenant_id)
    if not source_snapshot_path:
        return JSONResponse({"error": f"No snapshot for source tenant {source_tenant_id}"}, status_code=404)

    try:
        source_data = json.loads(source_snapshot_path.read_text(encoding="utf-8"))
        applications = source_data.get("applications", [])
        selected_app = None
        for app in applications:
            if str(app.get("id")) == str(application_id):
                selected_app = app
                break
        if not selected_app:
            return JSONResponse({"error": "Application not found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": "Failed to read source snapshot"}, status_code=500)

    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        target_auth = TenantAuth(token_manager, tenant_id=target_tenant_id)
        snapshot_url = f"{config.AF_URL}{config.SNAPSHOT_ENDPOINT}"
        try:
            resp = await client.get(snapshot_url, auth=target_auth)
            resp.raise_for_status()
            target_snapshot = resp.json()
        except Exception as e:
            return JSONResponse({"error": f"Failed to fetch target snapshot: {str(e)}"}, status_code=500)

        target_apps = target_snapshot.get("applications", [])
        replaced = False
        for i, app in enumerate(target_apps):
            if str(app.get("id")) == str(application_id):
                target_apps[i] = selected_app
                replaced = True
                break
        if not replaced:
            target_apps.append(selected_app)
        target_snapshot["applications"] = target_apps

    content = json.dumps(target_snapshot, ensure_ascii=False, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=merged_snapshot_{target_tenant_id}.json"}
    )


@router.get("/ui", response_class=HTMLResponse)
async def ui():
    return HTMLResponse(INDEX_HTML)


@router.get("/api/tenants/{tenant_id}/applications")
async def api_tenant_applications(tenant_id: str):
    return get_applications_from_snapshot(tenant_id)


@router.post("/api/global_lists/check_ip")
async def api_check_ip_in_global_list(request: Request):
    """Проверяет наличие IP в глобальном списке."""
    body = await request.json()
    tenant_id = body.get("tenant_id")
    list_id = body.get("list_id")
    ip = body.get("ip", "").strip()
    
    if not ip:
        return JSONResponse({"error": "IP address is required"}, status_code=400)
    
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        # Для всех тенантов - проверяем Aggregation blacklist в каждом
        if tenant_id == "__all__":
            tenants = await fetch_tenants_with_snapshots()
            results = []
            
            for t in tenants:
                tid = str(t["id"])
                try:
                    # Получаем глобальные списки для тенанта
                    lists = await _fetch_global_lists(client, token_manager, tid)
                    # Ищем список с именем "Aggregation blacklist" или похожим
                    target_list = None
                    for gl in lists:
                        gl_name = gl.get("name", "").lower()
                        if "aggregation blacklist" in gl_name or gl_name == "aggregation blacklist":
                            target_list = gl
                            break
                    
                    if not target_list:
                        logger.debug(f"Aggregation blacklist not found for tenant {tid}")
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t.get("name") or t.get("displayName") or tid,
                            "found": False,
                            "message": "Aggregation blacklist not found"
                        })
                        continue
                    
                    # Получаем содержимое списка
                    gl_id = target_list.get("id")
                    file_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{gl_id}/file"
                    auth = TenantAuth(token_manager, tenant_id=tid)
                    
                    logger.debug(f"Fetching global list file from {file_url} for tenant {tid}")
                    file_resp = await client.get(file_url, auth=auth)
                    
                    if file_resp.status_code != 200:
                        logger.warning(f"Failed to fetch list content for tenant {tid}: HTTP {file_resp.status_code}")
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t.get("name") or t.get("displayName") or tid,
                            "list_name": target_list.get("name"),
                            "found": False,
                            "message": f"Failed to fetch list content: HTTP {file_resp.status_code}"
                        })
                        continue
                    
                    # Проверяем наличие IP в содержимом
                    content = file_resp.text
                    # logger.debug(f"Full content:\n{content}")
                    lines = content.splitlines()
                    found = False
                    ttl_remaining = None
                    in_subnet = False
                    containing_subnets = []
                    
                    for line in lines:
                        line = line.strip()
                        # Проверяем точное совпадение IP
                        if line == ip:
                            found = True
                            break
                        
                        # Проверяем, начинается ли строка с IP + пробел или точка с запятой
                        if line.startswith(ip + " ") or line.startswith(ip + ";"):
                            found = True
                            # Извлекаем остаток (дату или TTL)
                            rest = line[len(ip):].strip()
                            ttl_remaining = rest
                            break
                    
                    # Проверяем, является ли IP частью подсети
                    in_subnet, containing_subnets = is_ip_in_subnet(ip, content)
                    
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t.get("name") or t.get("displayName") or tid,
                        "list_name": target_list.get("name"),
                        "list_id": gl_id,
                        "found": found,
                        "in_subnet": in_subnet,
                        "containing_subnets": containing_subnets,
                        "ttl_remaining": ttl_remaining
                    })
                    
                except Exception as e:
                    logger.error(f"Error checking IP for tenant {tid}: {type(e).__name__}: {e}")
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t.get("name") or t.get("displayName") or tid,
                        "found": False,
                        "error": str(e)
                    })
            
            return {"results": results, "checked_ip": ip}
        
        else:
            # Конкретный тенант - используем выбранный список
            if not list_id:
                return JSONResponse({"error": "list_id is required for specific tenant"}, status_code=400)
            
            try:
                # Получаем содержимое списка
                file_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{list_id}/file"
                auth = TenantAuth(token_manager, tenant_id=tenant_id)
                
                logger.debug(f"Fetching global list file from {file_url} for tenant {tenant_id}")
                file_resp = await client.get(file_url, auth=auth)
                
                if file_resp.status_code != 200:
                    return JSONResponse({
                        "found": False,
                        "error": f"Failed to fetch list content: HTTP {file_resp.status_code}"
                    }, status_code=file_resp.status_code)
                
                content = file_resp.text
                # logger.debug(f"Full content:\n{content}")
                lines = content.splitlines()
                found = False
                ttl_remaining = None
                in_subnet = False
                containing_subnets = []
                
                for line in lines:
                    line = line.strip()
                    # Проверяем точное совпадение IP
                    if line == ip:
                        found = True
                        break
                    
                    # Проверяем, начинается ли строка с IP + пробел или точка с запятой
                    if line.startswith(ip + " ") or line.startswith(ip + ";"):
                        found = True
                        rest = line[len(ip):].strip()
                        ttl_remaining = rest
                        break
                
                # Проверяем, является ли IP частью подсети
                in_subnet, containing_subnets = is_ip_in_subnet(ip, content)
                
                return {
                    "found": found,
                    "checked_ip": ip,
                    "in_subnet": in_subnet,
                    "containing_subnets": containing_subnets,
                    "ttl_remaining": ttl_remaining
                }
                
            except Exception as e:
                logger.error(f"Error checking IP for tenant {tenant_id}: {type(e).__name__}: {e}")
                return JSONResponse({"found": False, "error": str(e)}, status_code=500)
            

@router.post("/api/global_lists/get_permanent_ips")
async def api_get_permanent_ips(request: Request):
    """Получает все IP с permanent TTL (без TTL) из глобального списка."""
    body = await request.json()
    tenant_id = body.get("tenant_id")
    list_id = body.get("list_id")
    
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        # Для всех тенантов - используем Aggregation blacklist
        if tenant_id == "__all__":
            tenants_with_lists = await _get_tenants_with_global_lists(client, "Aggregation blacklist")
            results = []
            
            for t in tenants_with_lists:
                tid = t["tenant_id"]
                list_id_for_tenant = t["list_id"]
                try:
                    file_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{list_id_for_tenant}/file"
                    auth = TenantAuth(token_manager, tenant_id=tid)
                    file_resp = await client.get(file_url, auth=auth)
                    
                    if file_resp.status_code != 200:
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t["tenant_name"],
                            "list_name": t["list_name"],
                            "error": f"HTTP {file_resp.status_code}",
                            "permanent_ips": []
                        })
                        continue
                    
                    content = file_resp.text
                    lines = content.splitlines()
                    permanent_ips = []
                    
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        # IP без TTL - это строка, которая не содержит пробелов/точек с запятой после IP
                        parts = line.split()
                        if len(parts) == 1:
                            # Это permanent IP
                            permanent_ips.append(line)
                    
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t["tenant_name"],
                        "list_name": t["list_name"],
                        "list_id": list_id_for_tenant,
                        "permanent_ips": permanent_ips,
                        "count": len(permanent_ips)
                    })
                    
                except Exception as e:
                    logger.error(f"Error getting permanent IPs for tenant {tid}: {type(e).__name__}: {e}")
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t["tenant_name"],
                        "error": str(e),
                        "permanent_ips": []
                    })
            
            total_permanent = sum(len(r.get("permanent_ips", [])) for r in results)
            return {"results": results, "total_permanent_ips": total_permanent}
        
        else:
            # Конкретный тенант
            if not list_id:
                return JSONResponse({"error": "list_id is required for specific tenant"}, status_code=400)
            
            try:
                file_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{list_id}/file"
                auth = TenantAuth(token_manager, tenant_id=tenant_id)
                file_resp = await client.get(file_url, auth=auth)
                
                if file_resp.status_code != 200:
                    return JSONResponse({
                        "error": f"Failed to fetch list content: HTTP {file_resp.status_code}",
                        "permanent_ips": []
                    }, status_code=file_resp.status_code)
                
                content = file_resp.text
                lines = content.splitlines()
                permanent_ips = []
                
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # IP без TTL - это строка, которая не содержит пробелов/точек с запятой после IP
                    parts = line.split()
                    if len(parts) == 1:
                        permanent_ips.append(line)
                
                return {
                    "tenant_id": tenant_id,
                    "list_id": list_id,
                    "permanent_ips": permanent_ips,
                    "count": len(permanent_ips)
                }
                
            except Exception as e:
                logger.error(f"Error getting permanent IPs for tenant {tenant_id}: {type(e).__name__}: {e}")
                return JSONResponse({"error": str(e), "permanent_ips": []}, status_code=500)


@router.post("/api/global_lists/set_permanent_ips_7_days")
async def api_set_permanent_ips_7_days(request: Request):
    """Устанавливает TTL 7 дней (10080 минут) для всех IP с permanent TTL (без TTL) из глобального списка.
    Схема: сначала удаляем permanent IP, потом добавляем его же с TTL 7 дней."""
    body = await request.json()
    tenant_id = body.get("tenant_id")
    list_id = body.get("list_id")
    
    TTL_7_DAYS = 10080  # 7 * 24 * 60 = 10080 минут
    
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        # Для всех тенантов - используем Aggregation blacklist
        if tenant_id == "__all__":
            tenants_with_lists = await _get_tenants_with_global_lists(client, "Aggregation blacklist")
            results = []
            
            for t in tenants_with_lists:
                tid = t["tenant_id"]
                list_id_for_tenant = t["list_id"]
                try:
                    # Сначала получаем permanent IPs
                    file_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{list_id_for_tenant}/file"
                    auth = TenantAuth(token_manager, tenant_id=tid)
                    file_resp = await client.get(file_url, auth=auth)
                    
                    if file_resp.status_code != 200:
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t["tenant_name"],
                            "list_name": t["list_name"],
                            "status": "ERROR",
                            "error": f"HTTP {file_resp.status_code}",
                            "processed_count": 0
                        })
                        continue
                    
                    content = file_resp.text
                    lines = content.splitlines()
                    permanent_ips = []
                    
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split()
                        if len(parts) == 1:
                            permanent_ips.append(line)
                    
                    if not permanent_ips:
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t["tenant_name"],
                            "list_name": t["list_name"],
                            "status": "OK",
                            "message": "No permanent IPs found",
                            "processed_count": 0
                        })
                        continue
                    
                    # Шаг 1: Удаляем permanent IPs
                    remove_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/remove_items"
                    remove_payload = {"global_lists": [list_id_for_tenant], "items": permanent_ips}
                    remove_resp = await client.post(remove_url, json=remove_payload, auth=auth)
                    remove_resp.raise_for_status()
                    
                    # Шаг 2: Добавляем те же IP с TTL 7 дней
                    add_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/add_items"
                    add_payload = {"global_lists": [list_id_for_tenant], "items": permanent_ips, "ttl": TTL_7_DAYS}
                    add_resp = await client.post(add_url, json=add_payload, auth=auth)
                    add_resp.raise_for_status()
                    
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t["tenant_name"],
                        "list_name": t["list_name"],
                        "status": "OK",
                        "processed_count": len(permanent_ips)
                    })
                    
                except Exception as e:
                    logger.error(f"Error setting 7 days TTL for tenant {tid}: {type(e).__name__}: {e}")
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t["tenant_name"],
                        "error": str(e),
                        "status": "ERROR",
                        "processed_count": 0
                    })
            
            total_processed = sum(r.get("processed_count", 0) for r in results)
            success_count = len([r for r in results if r.get("status") == "OK"])
            return {
                "results": results,
                "summary": {
                    "total_tenants": len(results),
                    "success": success_count,
                    "failed": len(results) - success_count,
                    "total_processed": total_processed
                }
            }
        
        else:
            # Конкретный тенант
            if not list_id:
                return JSONResponse({"error": "list_id is required for specific tenant"}, status_code=400)
            
            try:
                # Сначала получаем permanent IPs
                file_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{list_id}/file"
                auth = TenantAuth(token_manager, tenant_id=tenant_id)
                file_resp = await client.get(file_url, auth=auth)
                
                if file_resp.status_code != 200:
                    return JSONResponse({
                        "error": f"Failed to fetch list content: HTTP {file_resp.status_code}",
                        "processed_count": 0
                    }, status_code=file_resp.status_code)
                
                content = file_resp.text
                lines = content.splitlines()
                permanent_ips = []
                
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) == 1:
                        permanent_ips.append(line)
                
                if not permanent_ips:
                    return {
                        "status": "OK",
                        "message": "No permanent IPs found",
                        "processed_count": 0
                    }
                
                # Шаг 1: Удаляем permanent IPs
                remove_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/remove_items"
                remove_payload = {"global_lists": [list_id], "items": permanent_ips}
                remove_resp = await client.post(remove_url, json=remove_payload, auth=auth)
                remove_resp.raise_for_status()
                
                # Шаг 2: Добавляем те же IP с TTL 7 дней
                add_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/add_items"
                add_payload = {"global_lists": [list_id], "items": permanent_ips, "ttl": TTL_7_DAYS}
                add_resp = await client.post(add_url, json=add_payload, auth=auth)
                add_resp.raise_for_status()
                
                return {
                    "status": "OK",
                    "processed_count": len(permanent_ips),
                    "processed_ips": permanent_ips
                }
                
            except Exception as e:
                logger.error(f"Error setting 7 days TTL for tenant {tenant_id}: {type(e).__name__}: {e}")
                return JSONResponse({"error": str(e), "processed_count": 0}, status_code=500)


@router.post("/api/global_lists/remove_permanent_ips")
async def api_remove_permanent_ips(request: Request):
    """Удаляет все IP с permanent TTL (без TTL) из глобального списка."""
    body = await request.json()
    tenant_id = body.get("tenant_id")
    list_id = body.get("list_id")
    
    async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
        # Для всех тенантов - используем Aggregation blacklist
        if tenant_id == "__all__":
            tenants_with_lists = await _get_tenants_with_global_lists(client, "Aggregation blacklist")
            results = []
            
            for t in tenants_with_lists:
                tid = t["tenant_id"]
                list_id_for_tenant = t["list_id"]
                try:
                    # Сначала получаем permanent IPs
                    file_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{list_id_for_tenant}/file"
                    auth = TenantAuth(token_manager, tenant_id=tid)
                    file_resp = await client.get(file_url, auth=auth)
                    
                    if file_resp.status_code != 200:
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t["tenant_name"],
                            "list_name": t["list_name"],
                            "status": "ERROR",
                            "error": f"HTTP {file_resp.status_code}",
                            "removed_count": 0
                        })
                        continue
                    
                    content = file_resp.text
                    lines = content.splitlines()
                    permanent_ips = []
                    
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split()
                        if len(parts) == 1:
                            permanent_ips.append(line)
                    
                    if not permanent_ips:
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t["tenant_name"],
                            "list_name": t["list_name"],
                            "status": "OK",
                            "message": "No permanent IPs found",
                            "removed_count": 0
                        })
                        continue
                    
                    # Удаляем permanent IPs
                    remove_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/remove_items"
                    payload = {"global_lists": [list_id_for_tenant], "items": permanent_ips}
                    remove_resp = await client.post(remove_url, json=payload, auth=auth)
                    remove_resp.raise_for_status()
                    
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t["tenant_name"],
                        "list_name": t["list_name"],
                        "status": "OK",
                        "removed_count": len(permanent_ips)
                    })
                    
                except Exception as e:
                    logger.error(f"Error removing permanent IPs for tenant {tid}: {type(e).__name__}: {e}")
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t["tenant_name"],
                        "error": str(e),
                        "status": "ERROR",
                        "removed_count": 0
                    })
            
            total_removed = sum(r.get("removed_count", 0) for r in results)
            success_count = len([r for r in results if r.get("status") == "OK"])
            return {
                "results": results,
                "summary": {
                    "total_tenants": len(results),
                    "success": success_count,
                    "failed": len(results) - success_count,
                    "total_removed": total_removed
                }
            }
        
        else:
            # Конкретный тенант
            if not list_id:
                return JSONResponse({"error": "list_id is required for specific tenant"}, status_code=400)
            
            try:
                # Сначала получаем permanent IPs
                file_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/{list_id}/file"
                auth = TenantAuth(token_manager, tenant_id=tenant_id)
                file_resp = await client.get(file_url, auth=auth)
                
                if file_resp.status_code != 200:
                    return JSONResponse({
                        "error": f"Failed to fetch list content: HTTP {file_resp.status_code}",
                        "removed_count": 0
                    }, status_code=file_resp.status_code)
                
                content = file_resp.text
                lines = content.splitlines()
                permanent_ips = []
                
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) == 1:
                        permanent_ips.append(line)
                
                if not permanent_ips:
                    return {
                        "status": "OK",
                        "message": "No permanent IPs found",
                        "removed_count": 0
                    }
                
                # Удаляем permanent IPs
                remove_url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}/remove_items"
                payload = {"global_lists": [list_id], "items": permanent_ips}
                remove_resp = await client.post(remove_url, json=payload, auth=auth)
                remove_resp.raise_for_status()
                
                return {
                    "status": "OK",
                    "removed_count": len(permanent_ips),
                    "removed_ips": permanent_ips
                }
                
            except Exception as e:
                logger.error(f"Error removing permanent IPs for tenant {tenant_id}: {type(e).__name__}: {e}")
                return JSONResponse({"error": str(e), "removed_count": 0}, status_code=500)
            

# ---------- Policy Manager Functions ----------
def _add_whitelist_precondition(rule: Dict[str, Any], whitelist_name: str) -> bool:
    """
    Добавляет white_list precondition к правилу "Block visitors by IP address from correlator".
    Возвращает True, если изменение было внесено, False если уже существует или правило не найдено.
    """
    if rule.get("name") != "Block visitors by IP address from correlator":
        return False
    
    params = rule.get("params", {})
    preconditions = params.get("preconditions", [])
    
    # Проверяем, есть ли уже такой precondition
    new_precondition = {
        "group": [
            {
                "condition": {
                    "global_param_type": "GLOBAL_LIST_CIDR",
                    "operator": "in",
                    "value": whitelist_name
                },
                "source": "CLIENT_IP"
            }
        ]
    }
    
    # Проверяем существование такого же precondition
    for existing in preconditions:
        if existing == new_precondition:
            logger.debug("Precondition already exists, skipping")
            return False
    
    # Добавляем новый precondition
    if not preconditions:
        params["preconditions"] = [new_precondition]
    else:
        preconditions.append(new_precondition)
    
    rule["params"] = params
    return True


def _modify_snapshot_for_policy(data: Dict[str, Any], whitelist_name: str) -> tuple[Dict[str, Any], bool, int]:
    """
    Модифицирует снапшот, добавляя white_list precondition к правилу во всех user_templates и policies приложений.
    Возвращает: (modified_data, changed, rules_modified_count)
    """
    modified_data = copy.deepcopy(data)
    rules_modified_count = 0
    
    # Модифицируем user_templates[].system_rules
    user_templates = modified_data.get("user_templates", [])
    for tpl in user_templates:
        system_rules = tpl.get("system_rules", [])
        for rule in system_rules:
            if _add_whitelist_precondition(rule, whitelist_name):
                rules_modified_count += 1
    
    # Собираем имена политик, используемых приложениями
    policy_names_in_use = set()
    for app in modified_data.get("applications", []):
        policy_name = app.get("policy", {}).get("name")
        if policy_name:
            policy_names_in_use.add(policy_name)
    
    # Модифицируем только используемые политики
    policies = modified_data.get("policies", [])
    for policy in policies:
        policy_name = policy.get("name")
        if policy_name not in policy_names_in_use:
            continue  # Пропускаем неиспользуемые политики
        system_rules = policy.get("system_rules", [])
        for rule in system_rules:
            if _add_whitelist_precondition(rule, whitelist_name):
                rules_modified_count += 1
    
    changed = rules_modified_count > 0
    return modified_data, changed, rules_modified_count


def _whitelist_exists_in_snapshot(data: Dict[str, Any], whitelist_name: str) -> bool:
    """
    Проверяет, существует ли global list с именем whitelist_name в снапшоте.
    """
    global_lists = data.get("global_lists", [])
    for gl in global_lists:
        if gl.get("name") == whitelist_name:
            return True
    return False


@router.post("/api/policy/download")
async def api_policy_download(request: Request):
    """
    Скачать модифицированный JSON снапшот с добавленным white_list precondition.
    Берёт данные из RAM кэша снапшотов.
    """
    try:
        body = await request.json()
        tenant_id = body.get("tenant_id")
        add_whitelist = body.get("add_whitelist", False)
        whitelist_name = body.get("whitelist_name", "white_list")
        
        if not tenant_id or tenant_id == "__all__":
            return JSONResponse({"error": "Specific tenant_id is required for download"}, status_code=400)
        
        if not add_whitelist:
            return JSONResponse({"error": "No modification option selected"}, status_code=400)
        
        # Получаем снапшот из RAM кэша
        from .snapshots import get_snapshot_cache
        
        cache = get_snapshot_cache()
        if not cache:
            return JSONResponse({
                "error": "Snapshot cache is empty. Please reload tenants from Main tab first."
            }, status_code=404)
        
        if tenant_id not in cache:
            return JSONResponse({
                "error": f"Snapshot for tenant {tenant_id} not found in cache. Please reload tenants first."
            }, status_code=404)
        
        data = cache.get(tenant_id)
        
        # Проверяем существование white_list
        if not _whitelist_exists_in_snapshot(data, whitelist_name):
            return JSONResponse({
                "error": f"Global list '{whitelist_name}' not found in snapshot. Please create it first."
            }, status_code=400)
        
        # Модифицируем снапшот
        modified_data, changed, rules_count = _modify_snapshot_for_policy(data, whitelist_name)
        
        logger.info(f"Policy download: tenant={tenant_id}, whitelist={whitelist_name}, rules_modified={rules_count}")
        
        content = json.dumps(modified_data, ensure_ascii=False, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=policy_{tenant_id}.json"}
        )
        
    except Exception as e:
        logger.error(f"Policy download error: {type(e).__name__}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/policy/apply")
async def api_policy_apply(request: Request):
    """
    Применить модификации снапшота (добавить white_list precondition) к тенанту(ам).
    """
    try:
        body = await request.json()
        tenant_id = body.get("tenant_id")
        add_whitelist = body.get("add_whitelist", False)
        whitelist_name = body.get("whitelist_name", "white_list")
        
        if not add_whitelist:
            return JSONResponse({"error": "No modification option selected"}, status_code=400)
        
        from .snapshots import get_snapshot_cache, export_snapshot_for_tenant
        from .tenants import fetch_tenants
        
        async with httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=config.REQUEST_TIMEOUT) as client:
            # Определяем список тенантов для обработки
            if tenant_id == "__all__":
                tenants = await fetch_tenants(client, token_manager)
                if not tenants:
                    return JSONResponse({"error": "No tenants found"}, status_code=404)
            else:
                tenant = await find_tenant(tenant_id)
                if not tenant:
                    return JSONResponse({"error": f"Tenant {tenant_id} not found"}, status_code=404)
                tenants = [tenant]
            
            results = []
            
            for t in tenants:
                tid = str(t.get("id"))
                t_name = t.get("name") or t.get("displayName") or tid
                
                try:
                    # Получаем снапшот
                    cache = get_snapshot_cache()
                    if tid not in cache:
                        await export_snapshot_for_tenant(client, token_manager, t)
                        cache = get_snapshot_cache()
                    
                    data = cache.get(tid)
                    if not data:
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t_name,
                            "error": "Snapshot not found"
                        })
                        continue
                    
                    # Проверяем существование white_list
                    if not _whitelist_exists_in_snapshot(data, whitelist_name):
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t_name,
                            "error": f"Global list '{whitelist_name}' not found in snapshot"
                        })
                        continue
                    
                    # Модифицируем снапшот
                    modified_data, changed, rules_count = _modify_snapshot_for_policy(data, whitelist_name)
                    
                    if not changed:
                        logger.info(f"Policy apply: tenant={tid} - no changes needed (already applied)")
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t_name,
                            "skipped": True,
                            "message": "No changes needed (already applied)"
                        })
                        continue
                    
                    logger.info(f"Policy apply: tenant={tid}, whitelist={whitelist_name}, rules_modified={rules_count}")
                    
                    # Импортируем модифицированный снапшот
                    auth = TenantAuth(token_manager, tenant_id=tid)
                    import_url = f"{config.AF_URL}{config.SNAPSHOT_IMPORT_TASKS_ENDPOINT}"
                    
                    import_resp = await client.post(import_url, json=modified_data, auth=auth)
                    if import_resp.status_code != 201:
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t_name,
                            "error": f"Import task failed: {import_resp.text[:200]}"
                        })
                        continue
                    
                    task = import_resp.json()
                    task_id = task.get("id")
                    
                    # Ожидание завершения задачи
                    status_url = f"{config.AF_URL}{config.SNAPSHOT_IMPORT_TASKS_ENDPOINT}"
                    success = False
                    for _ in range(30):
                        await asyncio.sleep(2)
                        try:
                            status_resp = await client.get(status_url, auth=auth)
                            status_resp.raise_for_status()
                            tasks = status_resp.json().get("items", [])
                            for tsk in tasks:
                                if tsk.get("id") == task_id:
                                    status = tsk.get("status")
                                    if status == "SUCCESS":
                                        success = True
                                        break
                                    elif status == "FAILED":
                                        results.append({
                                            "tenant_id": tid,
                                            "tenant_name": t_name,
                                            "error": "Import task failed"
                                        })
                                        break
                                    break
                        except Exception:
                            pass
                        if success:
                            break
                    
                    # Обновляем кэш снапшотов после успешного импорта (один раз)
                    if success:
                        await export_snapshot_for_tenant(client, token_manager, t)
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t_name,
                            "success": True,
                            "rules_modified": rules_count
                        })
                    elif not any(r.get("tenant_id") == tid and r.get("error") for r in results):
                        # Если ещё не добавлена ошибка и не success
                        results.append({
                            "tenant_id": tid,
                            "tenant_name": t_name,
                            "error": "Import task timeout"
                        })
                    
                except Exception as e:
                    logger.error(f"Error processing tenant {tid}: {type(e).__name__}: {e}")
                    results.append({
                        "tenant_id": tid,
                        "tenant_name": t_name,
                        "error": str(e)
                    })
            
            return {"results": results}
            
    except Exception as e:
        logger.error(f"Policy apply error: {type(e).__name__}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# Корневой маршрут
@router.get("/")
async def index():
    return {"message": "PTAF PRO web tools – backend is running.", "docs": "/docs", "ui": "/ui"}

