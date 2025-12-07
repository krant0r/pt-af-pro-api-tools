from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger

from .auth import TokenManager
from .config import config
from .rules_actions import (
    export_actions_for_tenant,
    export_rules_for_tenant,
    import_action_payload,
    import_rule_payload,
    list_local_exports,
    load_local_payload,
)

from .snapshots import (
    cleanup_old_snapshots,
    export_all_tenant_snapshots,
    export_snapshot_for_tenant,
    list_local_snapshots,
    latest_snapshot_per_tenant,
    load_snapshot_file,
)
from .tenants import fetch_tenants

app = FastAPI(
    title="PTAF PRO Web API Tools",
    description=(
        "Experimental web UI / API for working with PTAF PRO configuration.\n"
        "Stage 1: initialization – export full snapshots for all tenants.\n"
        "Extra: export/import rules & actions, simple web UI with EN/RU."
    ),
    version="0.2.0",
)

token_manager = TokenManager()


@app.on_event("startup")
async def _startup() -> None:
    logger.add(str(config.LOG_FILE), level=config.LOG_LEVEL)
    removed = cleanup_old_snapshots()
    if removed:
        logger.info(f"Startup cleanup: {removed} old snapshots removed")
    logger.info("Application startup complete")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Tenants helper
# ---------------------------------------------------------------------------


async def _fetch_tenants() -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        tenants = await fetch_tenants(client, token_manager)

    last_snapshots = latest_snapshot_per_tenant()
    for tenant in tenants:
        tenant_id = str(tenant.get("id") or "")
        if tenant_id and tenant_id in last_snapshots:
            tenant["last_snapshot_at"] = last_snapshots[tenant_id]
        else:
            tenant["last_snapshot_at"] = None

    return tenants


async def _find_tenant(
    tenant_id: str,
) -> Optional[Dict[str, Any]]:
    tenants = await _fetch_tenants()
    for t in tenants:
        if str(t.get("id")) == tenant_id:
            return t
    return None


def _settings_payload() -> Dict[str, Any]:
    return {
        "theme": config.UI_THEME,
        "language": config.UI_LANGUAGE,
        "af_url": config.AF_URL,
        "api_login": config.API_LOGIN,
        "api_password": config.API_PASSWORD,
        "verify_ssl": config.VERIFY_SSL,
        "ldap_auth": config.LDAP_AUTH,
        "snapshot_retention_days": config.SNAPSHOT_RETENTION_DAYS,
    }


@app.get("/api/settings")
async def api_get_settings():
    return _settings_payload()


@app.post("/api/settings")
async def api_save_settings(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        return JSONResponse({"error": "Invalid JSON payload"}, status_code=400)

    updates: Dict[str, Any] = {}
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

    return _settings_payload()


# ---------------------------------------------------------------------------
# API: snapshots
# ---------------------------------------------------------------------------


@app.post("/api/init/snapshots")
async def init_snapshots():
    """
    Стартовая стадия — экспорт снапшотов всех тенантов.
    """
    paths = await export_all_tenant_snapshots(token_manager)
    return JSONResponse(
        {
            "snapshots_written": len(paths),
            "files": [str(p) for p in paths],
        }
    )


@app.get("/api/tenants")
async def api_tenants():
    tenants = await _fetch_tenants()
    return tenants


@app.post("/api/tenants/{tenant_id}/snapshot")
async def api_snapshot_tenant(tenant_id: str):
    tenant = await _find_tenant(tenant_id)
    if not tenant:
        return JSONResponse(
            {"error": f"Tenant {tenant_id} not found"},
            status_code=404,
        )

    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        path = await export_snapshot_for_tenant(
            client,
            token_manager,
            tenant,
        )

    if not path:
        return JSONResponse(
            {"error": "Snapshot export failed"},
            status_code=500,
        )

    return {
        "file": str(path),
    }


@app.get("/api/snapshots/local")
async def api_list_snapshots_local():
    """
    Отдаёт список локальных снепшотов (только файловая система).
    """

    return {"snapshots": list_local_snapshots()}


@app.get("/api/snapshots/local/{filename}")
async def api_snapshot_file(filename: str):
    try:
        payload = load_snapshot_file(filename)
    except FileNotFoundError:
        return JSONResponse(
            {"error": "Snapshot file not found"},
            status_code=404,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    return {"filename": filename, "payload": payload}


# ---------------------------------------------------------------------------
# API: rules / actions
# ---------------------------------------------------------------------------


@app.post("/api/tenants/{tenant_id}/rules/export")
async def api_export_rules(tenant_id: str):
    tenant = await _find_tenant(tenant_id)
    if not tenant:
        return JSONResponse(
            {"error": f"Tenant {tenant_id} not found"},
            status_code=404,
        )

    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        files = await export_rules_for_tenant(client, token_manager, tenant)

    return {
        "exported": len(files),
        "files": [str(p) for p in files],
    }


@app.post("/api/tenants/{tenant_id}/actions/export")
async def api_export_actions(tenant_id: str):
    tenant = await _find_tenant(tenant_id)
    if not tenant:
        return JSONResponse(
            {"error": f"Tenant {tenant_id} not found"},
            status_code=404,
        )

    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        files = await export_actions_for_tenant(client, token_manager, tenant)

    return {
        "exported": len(files),
        "files": [str(p) for p in files],
    }


@app.post("/api/tenants/{tenant_id}/rules/import")
async def api_import_rule(
    tenant_id: str,
    file: UploadFile = File(...),
):
    """
    Импорт ОДНОГО правила из загруженного JSON-файла.
    """
    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return JSONResponse(
            {"error": "Invalid JSON in uploaded file"},
            status_code=400,
        )

    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        result = await import_rule_payload(
            client,
            token_manager,
            tenant_id,
            payload,
        )

    return result


@app.post("/api/tenants/{tenant_id}/actions/import")
async def api_import_action(
    tenant_id: str,
    file: UploadFile = File(...),
):
    """
    Импорт ОДНОГО действия из загруженного JSON-файла.
    """
    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return JSONResponse(
            {"error": "Invalid JSON in uploaded file"},
            status_code=400,
        )

    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        result = await import_action_payload(
            client,
            token_manager,
            tenant_id,
            payload,
        )

    return result


@app.get("/api/local-imports")
async def api_list_local_imports():
    """
    Возвращает список экспортированных правил/действий, доступных в файловой системе.
    """

    return {
        "rules": list_local_exports(config.RULES_DIR, "rule"),
        "actions": list_local_exports(config.ACTIONS_DIR, "action"),
    }


@app.post("/api/tenants/{tenant_id}/rules/import/local")
async def api_import_rule_local(tenant_id: str, request: Request):
    payload = await request.json()
    source_tenant = str(payload.get("source_tenant") or "").strip()
    filename = str(payload.get("filename") or "").strip()

    if not source_tenant or not filename:
        return JSONResponse(
            {"error": "source_tenant and filename are required"},
            status_code=400,
        )

    try:
        local_payload = load_local_payload(
            config.RULES_DIR, source_tenant, filename, "rule"
        )
    except FileNotFoundError:
        return JSONResponse(
            {"error": "Requested rule file not found for the specified tenant"},
            status_code=404,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        result = await import_rule_payload(
            client,
            token_manager,
            tenant_id,
            local_payload,
        )

    return result


@app.post("/api/tenants/{tenant_id}/actions/import/local")
async def api_import_action_local(tenant_id: str, request: Request):
    payload = await request.json()
    source_tenant = str(payload.get("source_tenant") or "").strip()
    filename = str(payload.get("filename") or "").strip()

    if not source_tenant or not filename:
        return JSONResponse(
            {"error": "source_tenant and filename are required"},
            status_code=400,
        )

    try:
        local_payload = load_local_payload(
            config.ACTIONS_DIR, source_tenant, filename, "action"
        )
    except FileNotFoundError:
        return JSONResponse(
            {"error": "Requested action file not found for the specified tenant"},
            status_code=404,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        result = await import_action_payload(
            client,
            token_manager,
            tenant_id,
            local_payload,
        )

    return result


# ---------------------------------------------------------------------------
# Простая веб-страница UI (EN/RU)
# ---------------------------------------------------------------------------

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>PTAF PRO Web Tools</title>
  <style>
    :root {
      --bg-color: #ffffff;
      --text-color: #0f172a;
      --border-color: #cbd5e1;
      --panel-bg: #f8fafc;
      --accent-color: #1d4ed8;
    }

    body[data-theme="dark"] {
      --bg-color: #0b1220;
      --text-color: #e2e8f0;
      --border-color: #334155;
      --panel-bg: #111827;
      --accent-color: #38bdf8;
    }

    body {
      font-family: sans-serif;
      margin: 1.5rem;
      background: var(--bg-color);
      color: var(--text-color);
      transition: background 0.2s ease, color 0.2s ease;
    }

    button,
    select,
    input[type="file"] {
      background: var(--panel-bg);
      color: var(--text-color);
      border: 1px solid var(--border-color);
      padding: 0.4rem 0.6rem;
      border-radius: 6px;
    }

    button:hover,
    select:focus,
    input[type="file"]:focus {
      outline: 1px solid var(--accent-color);
    }

    .lang-switch {
      margin-bottom: 1rem;
      display: flex;
      gap: 0.5rem;
      align-items: center;
      flex-wrap: wrap;
    }

    .settings-panel {
      border: 1px solid var(--border-color);
      background: var(--panel-bg);
      padding: 1rem;
      border-radius: 10px;
      margin-bottom: 1rem;
      max-width: 520px;
    }

    .menu-panel {
      max-width: 720px;
    }

    .menu-list {
      margin: 0;
      padding-left: 1.2rem;
      display: flex;
      flex-direction: column;
      gap: 0.65rem;
    }

    .menu-list ol {
      margin-top: 0.4rem;
    }

    .menu-list li {
      line-height: 1.5;
    }

    .note {
      font-size: 0.9rem;
      color: #6b7280;
    }

    .snapshot-preview {
      white-space: pre-wrap;
      background: var(--panel-bg);
      border: 1px solid var(--border-color);
      padding: 0.75rem;
      border-radius: 8px;
      max-height: 260px;
      overflow: auto;
      font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    }

    .settings-row {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      margin-bottom: 0.75rem;
    }

    .settings-row label {
      font-weight: 600;
    }

    .settings-actions {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }

    .hidden { display: none; }

    .log {
      border: 1px solid var(--border-color);
      padding: 0.5rem;
      max-height: 300px;
      overflow-y: auto;
      background: var(--panel-bg);
      border-radius: 8px;
    }

    button { margin: 0.25rem 0.5rem 0.25rem 0; }
    select { min-width: 240px; }
    code { background: var(--panel-bg); padding: 0.1rem 0.3rem; border-radius: 4px; }
  </style>
</head>
<body data-theme="light">
  <div class="lang-switch">
    <button onclick="setLang('en')">EN</button>
    <button onclick="setLang('ru')">RU</button>
    <button id="theme-toggle" onclick="toggleTheme()">Dark theme</button>
    <button id="settings-toggle" onclick="toggleSettings()">⚙️ Settings</button>
  </div>

  <div id="settings-panel" class="settings-panel hidden">
    <h2 id="settings-title-en">Settings</h2>
    <h2 id="settings-title-ru" class="hidden">Настройки</h2>

    <div class="settings-row">
      <label>
        <span id="label-theme-en">Theme</span>
        <span id="label-theme-ru" class="hidden">Тема</span>
      </label>
      <select id="setting-theme">
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </div>

    <div class="settings-row">
      <label>
        <span id="label-language-en">Language</span>
        <span id="label-language-ru" class="hidden">Язык</span>
      </label>
      <select id="setting-language">
        <option value="en">EN</option>
        <option value="ru">RU</option>
      </select>
    </div>

    <div class="settings-row">
      <label>
        <span id="label-af-url-en">AF server URL</span>
        <span id="label-af-url-ru" class="hidden">Адрес сервера AF</span>
      </label>
      <input type="text" id="setting-af-url" placeholder="https://afpro.local" />
    </div>

    <div class="settings-row">
      <label>
        <span id="label-api-login-en">AF login</span>
        <span id="label-api-login-ru" class="hidden">Логин AF</span>
      </label>
      <input type="text" id="setting-api-login" placeholder="user@example" />
    </div>

    <div class="settings-row">
      <label>
        <span id="label-api-password-en">AF password</span>
        <span id="label-api-password-ru" class="hidden">Пароль AF</span>
      </label>
      <input type="password" id="setting-api-password" placeholder="••••••" />
    </div>

    <div class="settings-row">
      <label>
        <span id="label-verify-ssl-en">Verify SSL certificates</span>
        <span id="label-verify-ssl-ru" class="hidden">Проверять SSL сертификаты</span>
      </label>
      <label>
        <input type="checkbox" id="setting-verify-ssl" />
        <span id="hint-verify-ssl-en">Enable TLS verification for AF API</span>
        <span id="hint-verify-ssl-ru" class="hidden">Включить проверку TLS для AF API</span>
      </label>
    </div>

    <div class="settings-row">
      <label>
        <span id="label-ldap-auth-en">Use LDAP authentication</span>
        <span id="label-ldap-auth-ru" class="hidden">Использовать LDAP авторизацию</span>
      </label>
      <label>
        <input type="checkbox" id="setting-ldap-auth" />
        <span id="hint-ldap-auth-en">Send ldap=true when requesting tokens</span>
        <span id="hint-ldap-auth-ru" class="hidden">Отправлять ldap=true при получении токена</span>
      </label>
    </div>

    <div class="settings-row">
      <label>
        <span id="label-snapshot-retention-en">Snapshot retention (days)</span>
        <span id="label-snapshot-retention-ru" class="hidden">Хранить снапшоты (дней)</span>
      </label>
      <input
        type="number"
        id="setting-snapshot-retention"
        min="1"
        inputmode="numeric"
        placeholder="30"
      />
    </div>

    <div class="settings-actions">
      <button onclick="saveSettings()" id="settings-save-en">Save settings</button>
      <button onclick="saveSettings()" id="settings-save-ru" class="hidden">Сохранить</button>
      <button onclick="toggleSettings()" id="settings-close-en">Close</button>
      <button onclick="toggleSettings()" id="settings-close-ru" class="hidden">Закрыть</button>
    </div>
  </div>

  <h1 id="title-en">PTAF PRO Web Tools</h1>
  <h1 id="title-ru" class="hidden">PTAF PRO Web Tools (RU)</h1>

  <p id="desc-en">
    Minimal experimental web UI on top of FastAPI backend.<br/>
    Choose tenant, then run one of the numbered actions.<br/>
    These numbers correspond to CLI sequence codes.
  </p>
  <p id="desc-ru" class="hidden">
    Минимальный экспериментальный веб-интерфейс поверх FastAPI.<br/>
    Выбери тенант, затем запусти одно из пронумерованных действий.<br/>
    Эти номера совпадают с кодами действий в CLI-последовательности.
  </p>

  <div class="settings-panel menu-panel">
    <h2 id="menu-title-en">Interactive menu (mirrors CLI)</h2>
    <h2 id="menu-title-ru" class="hidden">Интерактивное меню (как в CLI)</h2>

    <ol class="menu-list">
      <li>
        <strong>1.</strong>
        <span id="menu-item1-en">Import rules</span>
        <span id="menu-item1-ru" class="hidden">Импорт правил</span>
        —
        <button onclick="scrollToImport()">Open import block</button>
      </li>
      <li>
        <strong>2.</strong>
        <span id="menu-item2-en">Export rules</span>
        <span id="menu-item2-ru" class="hidden">Экспорт правил</span>
        —
        <button onclick="runRulesExport()">Run for selected tenant</button>
      </li>
      <li>
        <strong>3.</strong>
        <span id="menu-item3-en">Policy templates</span>
        <span id="menu-item3-ru" class="hidden">Шаблоны политик</span>
        <div class="note" id="menu-note3-en">
          Snapshot-only UI: templates are not changed directly via API.
        </div>
        <div class="note hidden" id="menu-note3-ru">
          Работаем только со снепшотами: шаблоны политик через API не трогаем.
        </div>
      </li>
      <li>
        <strong>4.</strong>
        <span id="menu-item4-en">Traffic settings</span>
        <span id="menu-item4-ru" class="hidden">Настройки traffic_settings</span>
        <div class="note" id="menu-note4-en">
          Use exported snapshots for review; live API changes are disabled here.
        </div>
        <div class="note hidden" id="menu-note4-ru">
          Используйте выгруженные снепшоты для просмотра — прямые API-изменения отключены.
        </div>
      </li>
      <li>
        <strong>5.</strong>
        <span id="menu-item5-en">Actions in rules</span>
        <span id="menu-item5-ru" class="hidden">Управление действиями</span>
        —
        <button onclick="scrollToImport()">Work via exports/imports</button>
      </li>
      <li>
        <strong>6.</strong>
        <span id="menu-item6-en">Get tenant configurations</span>
        <span id="menu-item6-ru" class="hidden">Получение конфигураций</span>
        <ol>
          <li>
            <span id="menu-item6a-en">Current tenant snapshot</span>
            <span id="menu-item6a-ru" class="hidden">Снапшот выбранного тенанта</span>
            —
            <button onclick="runSingleSnapshot()">Run 6.1</button>
          </li>
          <li>
            <span id="menu-item6b-en">All tenants snapshots</span>
            <span id="menu-item6b-ru" class="hidden">Снапшоты всех тенантов</span>
            —
            <button onclick="runSnapshots()">Run 6.2</button>
          </li>
        </ol>
      </li>
      <li>
        <strong>7.</strong>
        <span id="menu-item7-en">Restore tenant configs (snapshots only)</span>
        <span id="menu-item7-ru" class="hidden">Восстановление конфигураций (снепшоты)</span>
        —
        <button onclick="scrollToSnapshots()">Open snapshot library</button>
      </li>
      <li>
        <strong>8.</strong>
        <span id="menu-item8-en">Move objects between tenants</span>
        <span id="menu-item8-ru" class="hidden">Перенос объектов между тенантами</span>
        <div class="note" id="menu-note8-en">
          Keep data in exports/imports; direct API migrations are out of scope for this UI.
        </div>
        <div class="note hidden" id="menu-note8-ru">
          Держим данные в экспортах/импортах; прямые миграции по API здесь не выполняются.
        </div>
      </li>
      <li>
        <strong>9.</strong>
        <span id="menu-item9-en">Dangerous actions</span>
        <span id="menu-item9-ru" class="hidden">Опасные действия</span>
        <div class="note" id="menu-note9-en">
          Not exposed in the web UI to avoid accidental API calls.
        </div>
        <div class="note hidden" id="menu-note9-ru">
          В веб-интерфейсе не отображаем, чтобы исключить случайные вызовы API.
        </div>
      </li>
    </ol>
  </div>

  <h2 id="section-tenant-en">1. Tenants</h2>
  <h2 id="section-tenant-ru" class="hidden">1. Тенанты</h2>

  <button onclick="loadTenants()">Reload tenants</button>
  <br/>
  <select id="tenant-select"></select>

  <div class="settings-actions">
    <code>1</code> –
    <span id="a1-en">Export snapshots for all tenants</span>
    <span id="a1-ru" class="hidden">Экспорт снапшотов всех тенантов</span>
    <button onclick="runSnapshots()">Run</button>
  </div>

  <h2 id="section-actions-en">2. Actions</h2>
  <h2 id="section-actions-ru" class="hidden">2. Действия</h2>

  <ul>
    <li>
      <code>2</code> –
      <span id="a2-en">Export rules for selected tenant</span>
      <span id="a2-ru" class="hidden">Экспорт правил для выбранного тенанта</span>
      <button onclick="runRulesExport()">Run</button>
    </li>
    <li>
      <code>3</code> –
      <span id="a3-en">Export actions for selected tenant</span>
      <span id="a3-ru" class="hidden">Экспорт действий для выбранного тенанта</span>
      <button onclick="runActionsExport()">Run</button>
    </li>
  </ul>

  <h2 id="section-import-en">3. Import rule / action JSON</h2>
  <h2 id="section-import-ru" class="hidden">3. Импорт JSON правил / действий</h2>

  <p>
    <span id="import-text-en">
      Select tenant, choose file and click import button.
    </span>
    <span id="import-text-ru" class="hidden">
      Выбери тенант, выбери файл и нажми нужную кнопку.
    </span>
  </p>

  <input type="file" id="file-input" />

  <div>
    <button onclick="importRule()">Import rule JSON</button>
    <button onclick="importAction()">Import action JSON</button>
  </div>

  <h3 id="local-import-title-en">Or use exported files from /data</h3>
  <h3 id="local-import-title-ru" class="hidden">
    Или выбери уже выгруженные файлы из /data
  </h3>

  <div class="settings-panel">
    <div class="settings-row">
      <label>
        <span id="local-rules-label-en">Rules from tenant (by name):</span>
        <span id="local-rules-label-ru" class="hidden">
          Правила из тенанта (по названию):
        </span>
      </label>
      <div class="settings-actions">
        <select id="local-rules-tenant" onchange="updateLocalFiles('rule')"></select>
        <select id="local-rules-file"></select>
        <button onclick="importRuleFromLocal()">Import selected rule</button>
      </div>
    </div>

    <div class="settings-row">
      <label>
        <span id="local-actions-label-en">Actions from tenant (by name):</span>
        <span id="local-actions-label-ru" class="hidden">
          Действия из тенанта (по названию):
        </span>
      </label>
      <div class="settings-actions">
        <select id="local-actions-tenant" onchange="updateLocalFiles('action')"></select>
        <select id="local-actions-file"></select>
        <button onclick="importActionFromLocal()">Import selected action</button>
      </div>
    </div>

    <button onclick="loadLocalExports()">Reload exported files list</button>
  </div>

  <h2 id="snapshot-library-en">Snapshot library</h2>
  <h2 id="snapshot-library-ru" class="hidden">Библиотека снепшотов</h2>

  <div class="settings-panel">
    <p>
      <span id="snapshot-note-en">
        Only filesystem exports/imports are used. Choose a snapshot file to inspect
        or reuse its payload manually.
      </span>
      <span id="snapshot-note-ru" class="hidden">
        Используем только файловые экспорты/импорты. Выбери файл снепшота, чтобы
        просмотреть его или использовать содержимое вручную.
      </span>
    </p>

    <div class="settings-actions">
      <button onclick="loadLocalSnapshots()" id="snapshot-reload-en">
        Reload local snapshots
      </button>
      <button
        onclick="loadLocalSnapshots()"
        id="snapshot-reload-ru"
        class="hidden"
      >
        Обновить список снепшотов
      </button>
    </div>

    <div class="settings-row">
      <label>
        <span id="snapshot-select-label-en">Available files</span>
        <span id="snapshot-select-label-ru" class="hidden">Доступные файлы</span>
      </label>
      <div class="settings-actions">
        <select id="snapshot-file-select"></select>
        <button onclick="viewSnapshotPayload()" id="snapshot-view-en">
          View payload
        </button>
        <button
          onclick="viewSnapshotPayload()"
          id="snapshot-view-ru"
          class="hidden"
        >
          Показать содержимое
        </button>
      </div>
    </div>

    <div class="settings-row">
      <label>
        <span id="snapshot-preview-title-en">Snapshot content (readonly)</span>
        <span id="snapshot-preview-title-ru" class="hidden">Содержимое снепшота (только просмотр)</span>
      </label>
      <div id="snapshot-preview" class="snapshot-preview">—</div>
    </div>
  </div>

  <h2 id="log-title-en">Log</h2>
  <h2 id="log-title-ru" class="hidden">Лог</h2>
  <div id="log" class="log"></div>

  <script>
    let currentLang = "ru";
    let currentTheme = "light";
    let localRuleExports = [];
    let localActionExports = [];
    let localSnapshots = [];

    function themeToggleText(theme, lang) {
      const lightText = lang === "ru" ? "Светлая тема" : "Light theme";
      const darkText = lang === "ru" ? "Тёмная тема" : "Dark theme";
      return theme === "light" ? darkText : lightText;
    }

    function setLang(lang) {
      currentLang = lang;
      const ids = [
        ["title-en", "title-ru"],
        ["desc-en", "desc-ru"],
        ["section-tenant-en", "section-tenant-ru"],
        ["section-actions-en", "section-actions-ru"],
        ["section-import-en", "section-import-ru"],
        ["import-text-en", "import-text-ru"],
        ["log-title-en", "log-title-ru"],
        ["a1-en", "a1-ru"],
        ["a2-en", "a2-ru"],
        ["a3-en", "a3-ru"],
        ["settings-title-en", "settings-title-ru"],
        ["label-theme-en", "label-theme-ru"],
        ["label-language-en", "label-language-ru"],
        ["label-af-url-en", "label-af-url-ru"],
        ["label-api-login-en", "label-api-login-ru"],
        ["label-api-password-en", "label-api-password-ru"],
        ["label-verify-ssl-en", "label-verify-ssl-ru"],
        ["hint-verify-ssl-en", "hint-verify-ssl-ru"],
        ["label-ldap-auth-en", "label-ldap-auth-ru"],
        ["hint-ldap-auth-en", "hint-ldap-auth-ru"],
        ["label-snapshot-retention-en", "label-snapshot-retention-ru"],
        ["settings-save-en", "settings-save-ru"],
        ["settings-close-en", "settings-close-ru"],
        ["local-import-title-en", "local-import-title-ru"],
        ["local-rules-label-en", "local-rules-label-ru"],
        ["local-actions-label-en", "local-actions-label-ru"],
        ["menu-title-en", "menu-title-ru"],
        ["menu-item1-en", "menu-item1-ru"],
        ["menu-item2-en", "menu-item2-ru"],
        ["menu-item3-en", "menu-item3-ru"],
        ["menu-note3-en", "menu-note3-ru"],
        ["menu-item4-en", "menu-item4-ru"],
        ["menu-note4-en", "menu-note4-ru"],
        ["menu-item5-en", "menu-item5-ru"],
        ["menu-item6-en", "menu-item6-ru"],
        ["menu-item6a-en", "menu-item6a-ru"],
        ["menu-item6b-en", "menu-item6b-ru"],
        ["menu-item7-en", "menu-item7-ru"],
        ["menu-item8-en", "menu-item8-ru"],
        ["menu-note8-en", "menu-note8-ru"],
        ["menu-item9-en", "menu-item9-ru"],
        ["menu-note9-en", "menu-note9-ru"],
        ["snapshot-library-en", "snapshot-library-ru"],
        ["snapshot-note-en", "snapshot-note-ru"],
        ["snapshot-select-label-en", "snapshot-select-label-ru"],
        ["snapshot-preview-title-en", "snapshot-preview-title-ru"],
        ["snapshot-reload-en", "snapshot-reload-ru"],
        ["snapshot-view-en", "snapshot-view-ru"],
      ];
      ids.forEach(([en, ru]) => {
        document.getElementById(en).classList.toggle("hidden", lang !== "en");
        document.getElementById(ru).classList.toggle("hidden", lang !== "ru");
      });

      document.getElementById("settings-toggle").textContent =
        lang === "ru" ? "⚙️ Настройки" : "⚙️ Settings";

      const languageSelect = document.getElementById("setting-language");
      if (languageSelect) {
        languageSelect.value = lang;
      }

      setTheme(currentTheme);
    }

    function setTheme(theme) {
      currentTheme = theme;
      document.body.setAttribute("data-theme", theme);
      const toggleText = themeToggleText(theme, currentLang);
      document.getElementById("theme-toggle").textContent = toggleText;
      const themeSelect = document.getElementById("setting-theme");
      if (themeSelect) {
        themeSelect.value = theme;
      }
    }

    function scrollToElementById(id) {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }

    function scrollToImport() {
      scrollToElementById("section-import-en");
    }

    function scrollToSnapshots() {
      scrollToElementById("snapshot-library-en");
    }

    function toggleTheme() {
      const next = currentTheme === "light" ? "dark" : "light";
      setTheme(next);
    }

    function toggleSettings() {
      document.getElementById("settings-panel").classList.toggle("hidden");
    }

    function log(msg) {
      const el = document.getElementById("log");
      const line = document.createElement("div");
      const now = new Date().toISOString();
      line.textContent = "[" + now + "] " + msg;
      el.prepend(line);
    }

    function formatSnapshotInfo(dateStr) {
      if (!dateStr) {
        return currentLang === "ru" ? "без снепшота" : "no snapshot";
      }

      const parsed = new Date(dateStr);
      const formatted = Number.isNaN(parsed.getTime())
        ? dateStr
        : parsed.toLocaleString();

      return currentLang === "ru"
        ? `снапшот: ${formatted}`
        : `snapshot: ${formatted}`;
    }

    async function loadSettings() {
      log("Loading settings...");
      try {
        const resp = await fetch("/api/settings");
        if (!resp.ok) {
          log("Error loading settings: " + resp.status);
          setLang(currentLang);
          setTheme(currentTheme);
          return;
        }
        const data = await resp.json();
        currentLang = data.language || currentLang;
        currentTheme = data.theme || currentTheme;

        document.getElementById("setting-language").value = currentLang;
        document.getElementById("setting-theme").value = currentTheme;
        document.getElementById("setting-af-url").value = data.af_url || "";
        document.getElementById("setting-api-login").value = data.api_login || "";
        document.getElementById("setting-api-password").value = data.api_password || "";
        document.getElementById("setting-verify-ssl").checked =
          data.verify_ssl !== false;
        document.getElementById("setting-ldap-auth").checked =
          !!data.ldap_auth;
        document.getElementById("setting-snapshot-retention").value =
          data.snapshot_retention_days ?? 30;

        setLang(currentLang);
        setTheme(currentTheme);
      } catch (e) {
        log("Error loading settings: " + e);
        setLang(currentLang);
        setTheme(currentTheme);
      }
    }

    async function saveSettings() {
      const payload = {
        theme: document.getElementById("setting-theme").value,
        language: document.getElementById("setting-language").value,
        af_url: document.getElementById("setting-af-url").value,
        api_login: document.getElementById("setting-api-login").value,
        api_password: document.getElementById("setting-api-password").value,
        verify_ssl: document.getElementById("setting-verify-ssl").checked,
        ldap_auth: document.getElementById("setting-ldap-auth").checked,
        snapshot_retention_days: (() => {
          const val = document
            .getElementById("setting-snapshot-retention")
            .value.trim();
          const num = Number(val);
          return Number.isFinite(num) && num > 0 ? num : null;
        })(),
      };

      log("Saving settings...");
      const resp = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await resp.json();
      if (!resp.ok) {
        log("Settings save failed: " + JSON.stringify(data));
        return;
      }

      log("Settings saved");
      currentLang = data.language || payload.language;
      currentTheme = data.theme || payload.theme;
      setLang(currentLang);
      setTheme(currentTheme);
      toggleSettings();
    }

    async function loadTenants() {
      log("Loading tenants...");
      const resp = await fetch("/api/tenants");
      if (!resp.ok) {
        log("Error loading tenants: " + resp.status);
        return;
      }
      const data = await resp.json();
      const select = document.getElementById("tenant-select");
      select.innerHTML = "";
      data.forEach((t) => {
        const opt = document.createElement("option");
        opt.value = t.id;
        const name = t.name || t.displayName || t.id;
        const snapshotInfo = formatSnapshotInfo(t.last_snapshot_at);
        opt.textContent = `${name} — ${snapshotInfo}`;
        select.appendChild(opt);
      });
      log("Loaded " + data.length + " tenants");
    }

    function getSelectedTenantId() {
      const select = document.getElementById("tenant-select");
      return select.value;
    }

    async function runSnapshots() {
      log("Running action 1 (snapshots for all tenants) [sequence: 1]");
      const resp = await fetch("/api/init/snapshots", { method: "POST" });
      const data = await resp.json();
      log("Snapshots result: " + JSON.stringify(data));
    }

    async function runSingleSnapshot() {
      const tenantId = getSelectedTenantId();
      if (!tenantId) {
        log("No tenant selected");
        return;
      }

      log(
        "Running action 6.1 (snapshot for tenant " +
          tenantId +
          ") [sequence: 6.1]"
      );
      const resp = await fetch(
        "/api/tenants/" + encodeURIComponent(tenantId) + "/snapshot",
        { method: "POST" }
      );
      const data = await resp.json();
      log("Single snapshot result: " + JSON.stringify(data));
    }

    async function runRulesExport() {
      const tenantId = getSelectedTenantId();
      if (!tenantId) {
        log("No tenant selected");
        return;
      }
      log(
        "Running action 2 (export rules for tenant " +
          tenantId +
          ") [sequence: 2]"
      );
      const resp = await fetch(
        "/api/tenants/" + encodeURIComponent(tenantId) + "/rules/export",
        { method: "POST" }
      );
      const data = await resp.json();
      log("Rules export result: " + JSON.stringify(data));
    }

    async function runActionsExport() {
      const tenantId = getSelectedTenantId();
      if (!tenantId) {
        log("No tenant selected");
        return;
      }
      log(
        "Running action 3 (export actions for tenant " +
          tenantId +
          ") [sequence: 3]"
      );
      const resp = await fetch(
        "/api/tenants/" + encodeURIComponent(tenantId) + "/actions/export",
        { method: "POST" }
      );
      const data = await resp.json();
      log("Actions export result: " + JSON.stringify(data));
    }

    async function importRule() {
      await importJsonTo("/rules/import");
    }

    async function importAction() {
      await importJsonTo("/actions/import");
    }

    function localData(kind) {
      return kind === "rule" ? localRuleExports : localActionExports;
    }

    function updateLocalSelects(kind) {
      const tenantsSelect = document.getElementById(
        `local-${kind}s-tenant`
      );
      const filesSelect = document.getElementById(`local-${kind}s-file`);
      const entries = localData(kind);

      tenantsSelect.innerHTML = "";
      filesSelect.innerHTML = "";

      entries.forEach((entry) => {
        const opt = document.createElement("option");
        opt.value = entry.tenant_name;
        opt.textContent = entry.tenant_name;
        tenantsSelect.appendChild(opt);
      });

      updateLocalFiles(kind);
    }

    function updateLocalFiles(kind) {
      const tenantsSelect = document.getElementById(
        `local-${kind}s-tenant`
      );
      const filesSelect = document.getElementById(`local-${kind}s-file`);
      const entries = localData(kind);

      filesSelect.innerHTML = "";
      const selected = entries.find(
        (e) => e.tenant_name === tenantsSelect.value
      );
      if (!selected) {
        return;
      }

      selected.files.forEach((fname) => {
        const opt = document.createElement("option");
        opt.value = fname;
        opt.textContent = fname;
        filesSelect.appendChild(opt);
      });
    }

    async function loadLocalExports() {
      const resp = await fetch("/api/local-imports");
      if (!resp.ok) {
        log("Failed to load local exports: " + resp.statusText);
        return;
      }
      const data = await resp.json();
      localRuleExports = data.rules || [];
      localActionExports = data.actions || [];
      updateLocalSelects("rule");
      updateLocalSelects("action");
      log(
        "Loaded local exports: " +
          `${localRuleExports.length} rule tenants, ${localActionExports.length} action tenants`
      );
    }

    function renderSnapshotSelect() {
      const select = document.getElementById("snapshot-file-select");
      select.innerHTML = "";

      localSnapshots.forEach((snap) => {
        const opt = document.createElement("option");
        const labelParts = [];
        if (snap.timestamp) labelParts.push(snap.timestamp);
        if (snap.tenant_label) labelParts.push(snap.tenant_label);
        if (snap.tenant_id) labelParts.push(`#${snap.tenant_id}`);
        opt.value = snap.filename;
        opt.textContent = labelParts.join(" · ") || snap.filename;
        select.appendChild(opt);
      });
    }

    async function loadLocalSnapshots() {
      const resp = await fetch("/api/snapshots/local");
      if (!resp.ok) {
        log("Failed to load local snapshots: " + resp.statusText);
        return;
      }
      const data = await resp.json();
      localSnapshots = data.snapshots || [];
      renderSnapshotSelect();
      if (!localSnapshots.length) {
        const preview = document.getElementById("snapshot-preview");
        if (preview) preview.textContent = "—";
      }
      log("Loaded local snapshots: " + localSnapshots.length);
    }

    async function viewSnapshotPayload() {
      const select = document.getElementById("snapshot-file-select");
      const filename = select.value;
      if (!filename) {
        log("Select snapshot file first");
        return;
      }

      log("Opening snapshot from filesystem: " + filename);
      const resp = await fetch(
        "/api/snapshots/local/" + encodeURIComponent(filename)
      );
      const data = await resp.json();
      if (!resp.ok) {
        log("Snapshot read failed: " + JSON.stringify(data));
        return;
      }

      const preview = document.getElementById("snapshot-preview");
      if (preview) {
        preview.textContent = JSON.stringify(data.payload, null, 2);
      }

      log("Snapshot loaded successfully: " + filename);
    }

    async function importRuleFromLocal() {
      await importFromLocal("rule");
    }

    async function importActionFromLocal() {
      await importFromLocal("action");
    }

    async function importFromLocal(kind) {
      const tenantId = getSelectedTenantId();
      if (!tenantId) {
        log("No tenant selected");
        return;
      }

      const tenantSelect = document.getElementById(`local-${kind}s-tenant`);
      const fileSelect = document.getElementById(`local-${kind}s-file`);
      const sourceTenant = tenantSelect.value;
      const filename = fileSelect.value;

      if (!sourceTenant || !filename) {
        log("Select exported tenant and file first");
        return;
      }

      const path =
        kind === "rule" ? "/rules/import/local" : "/actions/import/local";
      log(
        `Importing ${kind} from local export ${filename} (tenant ${sourceTenant})`
      );
      const resp = await fetch(
        `/api/tenants/${encodeURIComponent(tenantId)}${path}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_tenant: sourceTenant,
            filename: filename,
          }),
        }
      );
      const data = await resp.json();
      log("Import result: " + JSON.stringify(data));
    }

    async function importJsonTo(path) {
      const tenantId = getSelectedTenantId();
      if (!tenantId) {
        log("No tenant selected");
        return;
      }
      const fileInput = document.getElementById("file-input");
      if (!fileInput.files.length) {
        log("No file selected");
        return;
      }
      const file = fileInput.files[0];
      const form = new FormData();
      form.append("file", file);
      log("Uploading " + file.name + " to " + path + " for tenant " + tenantId);
      const resp = await fetch(
        "/api/tenants/" + encodeURIComponent(tenantId) + path,
        { method: "POST", body: form }
      );
      const data = await resp.json();
      log("Import result: " + JSON.stringify(data));
    }

    async function initUi() {
      await loadSettings();
      await loadTenants();
      await loadLocalExports();
      await loadLocalSnapshots();
      setTheme(currentTheme);
    }

    initUi().catch((e) => log("Error: " + e));
  </script>
</body>
</html>
"""


@app.get("/", response_class=JSONResponse)
async def index():
    return {
        "message": "PTAF PRO web tools – backend is running.",
        "docs": "/docs",
        "ui": "/ui",
    }


@app.get("/ui", response_class=HTMLResponse)
async def ui():
    return HTMLResponse(INDEX_HTML)
