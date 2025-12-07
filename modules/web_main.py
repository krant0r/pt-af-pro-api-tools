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
)

from .snapshots import (
    cleanup_old_snapshots,
    export_all_tenant_snapshots,
    export_snapshot_for_tenant,
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
        return await fetch_tenants(client, token_manager)


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
      <input type="text" id="setting-af-url" placeholder="https://ptaf.example.com" />
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

  <h2 id="section-tenant-en">1. Tenants</h2>
  <h2 id="section-tenant-ru" class="hidden">1. Тенанты</h2>

  <button onclick="loadTenants()">Reload tenants</button>
  <br/>
  <select id="tenant-select"></select>

  <h2 id="section-actions-en">2. Actions</h2>
  <h2 id="section-actions-ru" class="hidden">2. Действия</h2>

  <ul>
    <li>
      <code>1</code> –
      <span id="a1-en">Export snapshots for all tenants</span>
      <span id="a1-ru" class="hidden">Экспорт снапшотов всех тенантов</span>
      <button onclick="runSnapshots()">Run</button>
    </li>
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

  <h2 id="log-title-en">Log</h2>
  <h2 id="log-title-ru" class="hidden">Лог</h2>
  <div id="log" class="log"></div>

  <script>
    let currentLang = "ru";
    let currentTheme = "light";

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
        ["label-snapshot-retention-en", "label-snapshot-retention-ru"],
        ["settings-save-en", "settings-save-ru"],
        ["settings-close-en", "settings-close-ru"],
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
        opt.textContent = t.name || t.displayName || t.id;
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
