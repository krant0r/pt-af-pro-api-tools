# modules/web_ui.py

INDEX_HTML = """<!DOCTYPE html>
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

    .layout {
      max-width: 1280px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    /* Tab bar */
    .tab-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 1rem;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 0.5rem;
      flex-wrap: wrap;
    }
    .tab-buttons {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }
    .tab-button {
      background: none;
      border: none;
      padding: 0.5rem 1rem;
      cursor: pointer;
      font-size: 1rem;
      border-radius: 8px 8px 0 0;
      color: var(--text-color);
      transition: background 0.2s;
    }
    .tab-button.active {
      background: var(--accent-color);
      color: white;
    }
    .right-controls {
      display: flex;
      gap: 0.5rem;
      align-items: center;
    }
    .icon-btn {
      background: none;
      border: none;
      font-size: 1.3rem;
      cursor: pointer;
      padding: 0.3rem 0.5rem;
      border-radius: 6px;
      transition: background 0.2s;
    }
    .icon-btn:hover {
      background: var(--border-color);
    }
    .lang-toggle-btn {
      font-size: 1.5rem;
      background: none;
      border: none;
      cursor: pointer;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      transition: transform 0.1s;
    }
    .lang-toggle-btn:hover {
      transform: scale(1.1);
      background: var(--border-color);
    }

    .tab-content {
      display: none;
    }
    .tab-content.active {
      display: block;
    }

    /* Rest of the styles */
    .content {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .log-panel {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
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

    .settings-panel {
      border: 1px solid var(--border-color);
      background: var(--panel-bg);
      padding: 1rem;
      border-radius: 10px;
      margin-bottom: 1rem;
      max-width: 520px;
    }

    .settings-panel.slim {
      max-width: none;
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

    .transfer-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1rem;
      align-items: start;
    }

    .column-panel {
      background: var(--panel-bg);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }

    .panel-header {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
    }

    .chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem;
    }

    .chip {
      background: color-mix(in srgb, var(--accent-color) 12%, transparent);
      color: var(--text-color);
      border: 1px solid var(--border-color);
      border-radius: 999px;
      padding: 0.25rem 0.6rem;
      font-size: 0.9rem;
    }

    .two-cols {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1rem;
    }

    .subtle {
      color: #475569;
      margin: 0;
    }

    .hidden { display: none; }

    .log {
      border: 1px solid var(--border-color);
      padding: 0.5rem;
      height: 60vh;
      min-height: 240px;
      box-sizing: border-box;
      width: 100%;
      overflow-y: auto;
      background: var(--panel-bg);
      border-radius: 8px;
      font-family: monospace;
      font-size: 0.9rem;
    }
    
    .log div {
      padding: 0.25rem 0;
      border-bottom: 1px solid color-mix(in srgb, var(--border-color) 30%, transparent);
    }
    
    .log div:last-child {
      border-bottom: none;
    }

    .result-box {
      margin-top: 1rem;
      padding: 0.75rem;
      border-radius: 8px;
      background: var(--panel-bg);
      border: 1px solid var(--border-color);
      font-family: monospace;
      white-space: pre-wrap;
      word-break: break-word;
      transition: border-left-color 0.3s;
    }
    .result-box.success {
      border-left: 4px solid #27ae60;
      color: #27ae60;
    }
    .result-box.error {
      border-left: 4px solid #e74c3c;
      color: #e74c3c;
    }
    .result-box.info {
      border-left: 4px solid var(--accent-color);
    }

    button { margin: 0.25rem 0; }
    select { min-width: 240px; }
    code { background: var(--panel-bg); padding: 0.1rem 0.3rem; border-radius: 4px; }

    /* Vertical buttons group */
    .vertical-buttons {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      margin-top: 0.5rem;
    }
    .vertical-buttons button {
      width: 100%;
      text-align: left;
      padding: 0.5rem 0.75rem;
    }
    .section-title {
      font-weight: 600;
      margin: 0.5rem 0 0.25rem 0;
      font-size: 1rem;
      border-left: 3px solid var(--accent-color);
      padding-left: 0.5rem;
    }

    /* Loading overlay */
    #loading-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.5);
      backdrop-filter: blur(2px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      transition: opacity 0.3s ease;
    }
    .loading-content {
      background: var(--panel-bg);
      color: var(--text-color);
      padding: 1.5rem 2rem;
      border-radius: 16px;
      font-size: 1.2rem;
      font-weight: bold;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      display: flex;
      gap: 1rem;
      align-items: center;
    }
    .loading-spinner {
      width: 24px;
      height: 24px;
      border: 3px solid var(--border-color);
      border-top-color: var(--accent-color);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    @keyframes slideIn {
      from {
        transform: translateX(100%);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }
    .hidden-overlay {
      opacity: 0;
      visibility: hidden;
      transition: visibility 0.3s, opacity 0.3s;
    }
  </style>
</head>
<body data-theme="light">
  <div class="layout">
    <!-- Tab bar -->
    <div class="tab-bar">
      <div class="tab-buttons">
        <button class="tab-button active" data-tab="main" onclick="switchTab('main')">📋 Main</button>
        <button class="tab-button" data-tab="ip" onclick="switchTab('ip')">🌐 IP Management</button>
        <button class="tab-button" data-tab="policy" onclick="switchTab('policy')">🔒 Policy Manager</button>
        <button class="tab-button" data-tab="log" onclick="switchTab('log')">📜 Log</button>
        <button class="tab-button" data-tab="settings" onclick="switchTab('settings')">⚙️ Settings</button>
      </div>
      <div class="right-controls">
        <button class="icon-btn" id="theme-toggle" onclick="toggleTheme()">🌓</button>
        <button class="lang-toggle-btn" id="lang-toggle" onclick="toggleLanguage()">🇷🇺</button>
      </div>
    </div>

    <!-- Main tab -->
    <div id="tab-main" class="tab-content active">
      <div class="transfer-grid">
        <!-- LEFT COLUMN: export & actions -->
        <section class="column-panel">
          <div class="panel-header">
            <h2 id="from-title-en">From: what we export/import</h2>
            <h2 id="from-title-ru" class="hidden">Источник</h2>
          </div>
            <button onclick="loadTenants()">
              <span id="reload-tenants-en">🔄 Reload tenants</span>
              <span id="reload-tenants-ru" class="hidden">🔄 Обновить тенанты</span>
            </button>
          <div id="main-result" class="result-box info">
            <span id="main-result-placeholder-en">Ready</span>
            <span id="main-result-placeholder-ru" class="hidden">Готов</span>
          </div>
          <!-- Tenant & Application selection -->
          <div class="settings-row">
            <label>
              <span id="tenant-export-label-en">Tenant for export ("All tenants" supported):</span>
              <span id="tenant-export-label-ru" class="hidden">Тенант для экспорта (можно выбрать «Все тенанты»):</span>
            </label>
            <select id="tenant-select"></select>
            <small>
              <span id="tenant-export-hint-en">Use a specific tenant or run exports for all of them.</span>
              <span id="tenant-export-hint-ru" class="hidden">Можно выбрать конкретный тенант или запустить экспорт для всех.</span>
            </small>
          </div>

          <div class="settings-row">
            <label>
              <span id="source-app-label-en">Application (from snapshot)</span>
              <span id="source-app-label-ru" class="hidden">Приложение (из снапшота)</span>
            </label>
            <select id="source-application-select">
              <option value="">— select application —</option>
            </select>
            <small>
              <span id="source-app-hint-en">Choose an application from the source tenant’s latest snapshot.</span>
              <span id="source-app-hint-ru" class="hidden">Выберите приложение из последнего снапшота тенанта-источника.</span>
            </small>
          </div>

          <!-- BACKUP button -->
          <div class="section-title" id="backup-title-en">💾 Backup</div>
          <div class="section-title" id="backup-title-ru" class="hidden">💾 Бэкап</div>
          <div class="vertical-buttons">
            <button onclick="downloadBackup()" style="background: var(--accent-color); color: white; border: none;">
              <span id="backup-btn-en">📦 Download full backup (snapshots + rules + actions + global lists) as .tar.gz</span>
              <span id="backup-btn-ru" class="hidden">📦 Скачать полный бэкап (снапшоты + правила + действия + глобальные списки) в .tar.gz</span>
            </button>
          </div>
        </section>

        <!-- RIGHT COLUMN: import (unchanged) -->
        <section class="column-panel">
          <div class="panel-header">
            <h2 id="to-title-en">To: where we deliver</h2>
            <h2 id="to-title-ru" class="hidden">Получатель</h2>
          </div>

          <div class="settings-panel slim">
            <div class="settings-row">
              <label>
                <span id="tenant-import-label-en">Tenant(s) for import:</span>
                <span id="tenant-import-label-ru" class="hidden">Тенант(ы) для импорта:</span>
              </label>
              <select id="import-tenant-select"></select>
              <small id="tenant-import-hint-en">Choose specific tenant or "All tenants".</small>
              <small id="tenant-import-hint-ru" class="hidden">Выбери конкретный тенант или «Все тенанты».</small>
            </div>

            <div class="settings-actions">
              <button onclick="importApplicationToTarget()">
                <span id="import-app-button-en">⬇️ Import application</span>
                <span id="import-app-button-ru" class="hidden">⬇️ Импортировать приложение</span>
              </button>
              <button onclick="downloadMergedSnapshot()">
                <span id="download-json-button-en">💾 Download JSON</span>
                <span id="download-json-button-ru" class="hidden">💾 Скачать JSON</span>
              </button>
            </div>

            <div class="settings-row two-cols">
              <div>
                <label>
                  <span id="import-actions-title-en">Import action JSON</span>
                  <span id="import-actions-title-ru" class="hidden">Импорт JSON действия</span>
                </label>
                <input type="file" id="action-file-input" />
                <div class="settings-actions" style="margin-top: 0.5rem;">
                  <button onclick="importAction()">
                    <span id="import-action-btn-en">Import action JSON</span>
                    <span id="import-action-btn-ru" class="hidden">Импорт JSON действия</span>
                  </button>
                  <button onclick="downloadActionJson()">
                    <span id="download-action-json-btn-en">💾 Download JSON</span>
                    <span id="download-action-json-btn-ru" class="hidden">💾 Скачать JSON</span>
                  </button>
                </div>
              </div>
              <div>
                <label>
                  <span id="import-rules-title-en">Import rule JSON</span>
                  <span id="import-rules-title-ru" class="hidden">Импорт JSON правила</span>
                </label>
                <input type="file" id="rule-file-input" />
                <div class="settings-actions" style="margin-top: 0.5rem;">
                  <button onclick="importRule()">
                    <span id="import-rule-btn-en">Import rule JSON</span>
                    <span id="import-rule-btn-ru" class="hidden">Импорт JSON правила</span>
                  </button>
                  <button onclick="downloadRuleJson()">
                    <span id="download-rule-json-btn-en">💾 Download JSON</span>
                    <span id="download-rule-json-btn-ru" class="hidden">💾 Скачать JSON</span>
                  </button>
                </div>
              </div>
            </div>

            <div class="settings-row">
              <h3 id="local-import-title-en">Local exports → tenants</h3>
              <h3 id="local-import-title-ru" class="hidden">Локальные выгрузки → тенанты</h3>
              <p class="subtle">
                <span id="import-text-en">Choose target tenant(s) above, then pick what to import below.</span>
                <span id="import-text-ru" class="hidden">Выбери тенант(ы) для импорта выше, затем выбери источник ниже.</span>
              </p>
            </div>

            <div class="settings-row">
              <label>
                <span id="local-actions-label-en">Import action:</span>
                <span id="local-actions-label-ru" class="hidden">Импорт действия:</span>
              </label>
              <div class="settings-actions">
                <select id="local-actions-file"></select>
                <button onclick="importActionFromLocal()">
                  <span id="import-action-local-btn-en">Import selected action</span>
                  <span id="import-action-local-btn-ru" class="hidden">Импортировать выбранное действие</span>
                </button>
                <button onclick="downloadLocalActionJson()">
                  <span id="download-local-action-json-btn-en">💾 Download JSON</span>
                  <span id="download-local-action-json-btn-ru" class="hidden">💾 Скачать JSON</span>
                </button>
              </div>
            </div>

            <div class="settings-row">
              <label>
                <span id="local-rules-label-en">Import user rule:</span>
                <span id="local-rules-label-ru" class="hidden">Импорт пользовательского правила:</span>
              </label>
              <div class="settings-actions">
                <select id="local-rules-file"></select>
                <button onclick="importRuleFromLocal()">
                  <span id="import-rule-local-btn-en">Import selected rule</span>
                  <span id="import-rule-local-btn-ru" class="hidden">Импортировать выбранное правило</span>
                </button>
                <button onclick="downloadLocalRuleJson()">
                  <span id="download-local-rule-json-btn-en">💾 Download JSON</span>
                  <span id="download-local-rule-json-btn-ru" class="hidden">💾 Скачать JSON</span>
                </button>
              </div>
            </div>

            <div class="settings-actions">
              <button onclick="loadLocalExports()">
                <span id="reload-local-exports-en">🔄 Reload exported files and user rules</span>
                <span id="reload-local-exports-ru" class="hidden">🔄 Обновить файлы экспорта и правила</span>
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- IP Management tab -->
    <div id="tab-ip" class="tab-content">
      <div class="transfer-grid" style="margin-top: 1rem;">
        <section class="column-panel">
          <div class="panel-header">
            <h2 id="ip-title-en">🌐 IP Management (Add/Remove/Check)</h2>
            <h2 id="ip-title-ru" class="hidden">🌐 Управление IP (Добавить/Удалить/Проверить)</h2>
            <div class="chip-row">
              <span class="chip">Add IP</span>
              <span class="chip">Remove IP</span>
              <span class="chip">Check IP</span>
            </div>
          </div>
          <div class="settings-panel slim">
            <!-- Result display area (moved to top) -->
            <div id="ip-result" class="result-box info">
              <span id="ip-result-placeholder-en">Ready</span>
              <span id="ip-result-placeholder-ru" class="hidden">Готов</span>
            </div>

            <!-- Tenant selection -->
            <div class="settings-row">
              <label>
                <span id="ip-tenant-label-en">Tenant</span>
                <span id="ip-tenant-label-ru" class="hidden">Тенант</span>
              </label>
              <select id="ip-tenant" onchange="onIpTenantChange()"></select>
              <small id="ip-tenant-hint-en">Select tenant or "All tenants"</small>
              <small id="ip-tenant-hint-ru" class="hidden">Выберите тенант или "Все тенанты"</small>
            </div>

            <!-- Global list selection (hidden for "All tenants") -->
            <div class="settings-row" id="ip-list-row">
              <label>
                <span id="ip-list-label-en">Global list</span>
                <span id="ip-list-label-ru" class="hidden">Глобальный список</span>
              </label>
              <div class="settings-actions">
                <select id="ip-list" style="flex-grow:1" onchange="onIpListChange()"></select>
                <button onclick="loadIpLists()">🔄</button>
              </div>
              <small id="ip-list-hint-en">For "All tenants" checks "Aggregation blacklist" automatically</small>
              <small id="ip-list-hint-ru" class="hidden">Для "Все тенанты" автоматически проверяется "Aggregation blacklist"</small>
            </div>

            <!-- Create new global list section -->
            <div class="section-title" id="create-list-title-en">➕ Create New Global List</div>
            <div class="section-title hidden" id="create-list-title-ru">➕ Создать новый глобальный список</div>
            
            <div class="settings-row">
              <label>
                <span id="new-list-name-label-en">List name</span>
                <span id="new-list-name-label-ru" class="hidden">Название списка</span>
              </label>
              <input type="text" id="new-list-name" placeholder="my_white_list" />
            </div>
            
            <div class="settings-row">
              <label>
                <span id="new-list-type-label-en">List type</span>
                <span id="new-list-type-label-ru" class="hidden">Тип списка</span>
              </label>
              <select id="new-list-type">
                <option value="STATIC">STATIC (file-based, no TTL)</option>
                <option value="DYNAMIC">DYNAMIC (API-based, with TTL)</option>
              </select>
              <small id="new-list-type-hint-en">STATIC: upload file, no TTL. DYNAMIC: add/remove via API with TTL</small>
              <small id="new-list-type-hint-ru" class="hidden">STATIC: загрузка файла, без TTL. DYNAMIC: добавление через API с TTL</small>
            </div>
            
            <div class="settings-row" id="new-list-description-row">
              <label>
                <span id="new-list-description-label-en">Description (optional)</span>
                <span id="new-list-description-label-ru" class="hidden">Описание (опционально)</span>
              </label>
              <input type="text" id="new-list-description" placeholder="Optional description" />
            </div>
            
            <div class="settings-row" id="new-list-file-row">
              <label>
                <span id="new-list-file-label-en">File content (for STATIC lists, one IP per line)</span>
                <span id="new-list-file-label-ru" class="hidden">Содержимое файла (для STATIC списков, IP на строку)</span>
              </label>
              <textarea id="new-list-file" rows="5" placeholder="# Comment&#10;192.168.1.0/24&#10;10.0.0.1"></textarea>
              <small id="new-list-file-hint-en">Enter IP addresses, subnets, and comments. One per line.</small>
              <small id="new-list-file-hint-ru" class="hidden">Введите IP адреса, подсети и комментарии. По одному на строку.</small>
            </div>
            
            <div class="settings-row">
              <label>
                <input type="checkbox" id="new-list-force-overwrite" />
                <span id="new-list-force-label-en"> Force overwrite if list exists</span>
                <span id="new-list-force-label-ru" class="hidden"> Перезаписать, если список существует</span>
              </label>
              <small id="new-list-force-hint-en">If a list with this name exists, it will be overwritten</small>
              <small id="new-list-force-hint-ru" class="hidden">Если список с таким именем существует, он будет перезаписан</small>
            </div>
            
            <div class="settings-actions">
              <button onclick="createGlobalList()" style="background: #8e44ad; color: white; border: none;">✨ Create List</button>
            </div>

            <!-- IP address input -->
            <div class="settings-row">
              <label>
                <span id="ip-address-label-en">IP address</span>
                <span id="ip-address-label-ru" class="hidden">IP адрес</span>
              </label>
              <input type="text" id="ip-address" placeholder="192.168.1.1" />
              <small id="ip-address-hint-en">Single IP address for check, or comma-separated for add/remove</small>
              <small id="ip-address-hint-ru" class="hidden">Один IP для проверки, или через запятую для добавления/удаления</small>
            </div>

            <!-- TTL for add operation -->
            <div class="settings-row" id="ip-ttl-row">
              <label>
                <span id="ip-ttl-label-en">TTL (minutes, max 10080) - for Add operation</span>
                <span id="ip-ttl-label-ru" class="hidden">TTL (минуты, макс 10080) - для добавления</span>
              </label>
              <input type="number" id="ip-ttl" value="1440" min="1" max="10080" />
            </div>

            <!-- Action buttons -->
            <div class="settings-actions">
              <button onclick="addIp()" style="background: #27ae60; color: white; border: none;">➕ Add IP</button>
              <button onclick="removeIp()" style="background: #e67e22; color: white; border: none;">➖ Remove IP</button>
              <button onclick="checkIp()" style="background: #2980b9; color: white; border: none;">🔍 Check IP</button>
            </div>
            
            <!-- Permanent IP removal section -->
            <div class="section-title" id="permanent-ip-title-en">⚠️ Permanent IPs (no TTL)</div>
            <div class="section-title" id="permanent-ip-title-ru" class="hidden">⚠️ Permanent IP (без TTL)</div>
            <div class="settings-actions">
              <button onclick="getPermanentIps()" style="background: #9b59b6; color: white; border: none;">📋 Get Permanent IPs</button>
              <button onclick="setPermanentIps7Days()" style="background: #16a085; color: white; border: none;">🕒 Set 7 Days TTL</button>
              <button onclick="removePermanentIps()" style="background: #c0392b; color: white; border: none;">🗑️ Remove All Permanent IPs</button>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- Policy Manager tab -->
    <div id="tab-policy" class="tab-content">
      <div class="transfer-grid" style="margin-top: 1rem;">
        <section class="column-panel">
          <div class="panel-header">
            <h2 id="policy-title-en">🔒 Policy Manager (Batch Edit)</h2>
            <h2 id="policy-title-ru" class="hidden">🔒 Менеджер политик (Массовое редактирование)</h2>
            <div class="chip-row">
              <span class="chip">Add white_list exception</span>
              <span class="chip">All tenants or selected</span>
            </div>
          </div>
          <div class="settings-panel slim">
            <!-- Result display area -->
            <div id="policy-result" class="result-box info">
              <span id="policy-result-placeholder-en">Ready</span>
              <span id="policy-result-placeholder-ru" class="hidden">Готов</span>
            </div>

            <!-- Tenant selection -->
            <div class="settings-row">
              <label>
                <span id="policy-tenant-label-en">Tenant(s)</span>
                <span id="policy-tenant-label-ru" class="hidden">Тенант(ы)</span>
              </label>
              <select id="policy-tenant" onchange="onPolicyTenantChange()"></select>
              <small id="policy-tenant-hint-en">Select tenant or "All tenants"</small>
              <small id="policy-tenant-hint-ru" class="hidden">Выберите тенант или "Все тенанты"</small>
            </div>

            <!-- Rule modification options -->
            <div class="section-title" id="rule-mod-title-en">📝 Rule Modification Options</div>
            <div class="section-title" id="rule-mod-title-ru" class="hidden">📝 Опции изменения правил</div>
            
            <div class="settings-row">
              <label>
                <input type="checkbox" id="add-whitelist-to-aggregation-rule" />
                <span id="add-whitelist-label-en"> Add white_list to "Block visitors by IP address from correlator" rule</span>
                <span id="add-whitelist-label-ru" class="hidden"> Добавить white_list в правило "Block visitors by IP address from correlator"</span>
              </label>
              <small id="add-whitelist-hint-en">Adds white_list as an exception to the aggregation IP blocking rule in all web application policies</small>
              <small id="add-whitelist-hint-ru" class="hidden">Добавляет white_list как исключение к правилу блокировки IP агрегации во всех политиках web приложений</small>
            </div>

            <div class="settings-row">
              <label>
                <span id="whitelist-name-label-en">White list name</span>
                <span id="whitelist-name-label-ru" class="hidden">Название white списка</span>
              </label>
              <input type="text" id="whitelist-name" value="white_list" placeholder="white_list" />
              <small id="whitelist-name-hint-en">Name of the global list to use as white_list (must exist in snapshot)</small>
              <small id="whitelist-name-hint-ru" class="hidden">Название глобального списка для использования как white_list (должен существовать в снапшоте)</small>
            </div>

            <!-- Action buttons -->
            <div class="settings-actions" style="margin-top: 1rem;">
              <button onclick="downloadPolicyJson()" style="background: #3498db; color: white; border: none;">💾 Download JSON</button>
              <button onclick="applyPolicyChanges()" style="background: #27ae60; color: white; border: none;">✅ Apply Changes</button>
            </div>
          </div>
        </section>
      </div>
    </div>

    <div id="tab-log" class="tab-content">
      <div class="transfer-grid" style="margin-top: 1rem;">
        <section class="column-panel">
          <div class="panel-header">
            <h2 id="log-title-en">Log</h2>
            <h2 id="log-title-ru" class="hidden">Лог</h2>

          </div>
          <div id="log-result" class="result-box info">
            <span id="log-result-placeholder-en">Ready</span>
            <span id="log-result-placeholder-ru" class="hidden">Готов</span>
          </div>
          <!-- PRINT block (vertical buttons) -->
          <div class="section-title" id="print-title-en">📄 Print to log</div>
          <div class="section-title" id="print-title-ru" class="hidden">📄 Вывести в лог</div>
          <div class="vertical-buttons">
            <button onclick="logSnapshotApplications()">
              <span id="print-apps-en">📋 Print applications (from snapshots) to log</span>
              <span id="print-apps-ru" class="hidden">📋 Вывести приложения (из снапшотов) в лог</span>
            </button>
            <button onclick="logSnapshotHosts()">
              <span id="print-hosts-en">🌐 Print hosts (from snapshots) to log</span>
              <span id="print-hosts-ru" class="hidden">🌐 Вывести хосты (из снапшотов) в лог</span>
            </button>
            <button onclick="logSnapshotTenantHosts()">
              <span id="print-tenant-hosts-en">🏢 Print tenants + hosts (from snapshots) to log</span>
              <span id="print-tenant-hosts-ru" class="hidden">🏢 Вывести тенанты + хосты (из снапшотов) в лог</span>
            </button>
          </div>
          <h2 id="log-display-title-en">Log Output</h2>
          <h2 id="log-display-title-ru" class="hidden">Вывод лога</h2>
          <div id="log" class="log"></div>
        </section>
      </div>
    </div>

    <!-- Settings tab (unchanged) -->
    <div id="tab-settings" class="tab-content">
      <div class="settings-panel" style="max-width: 600px;">
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
          <input type="number" id="setting-snapshot-retention" min="1" inputmode="numeric" placeholder="30" />
        </div>

        <div class="settings-actions">
          <button onclick="saveSettings()" id="settings-save-en">Save settings</button>
          <button onclick="saveSettings()" id="settings-save-ru" class="hidden">Сохранить</button>
        </div>
      </div>
    </div>
  </div>

  <div id="loading-overlay" class="hidden-overlay">
    <div class="loading-content">
      <div class="loading-spinner"></div>
      <span id="loading-text-en">Initializing, please wait...</span>
      <span id="loading-text-ru" class="hidden">Инициализация, подождите...</span>
    </div>
  </div>

  <script>
    let currentLang = "ru";
    let currentTheme = "light";
    let localRuleExports = [];
    let localActionExports = [];
    let snapshotUserRules = [];
    let tenantsCache = [];
    let snapshotSummaryCache = null;
    let currentIpTenantLists = [];

    function setLang(lang) {
      currentLang = lang;
      // Update all bilingual elements
      const ids = [
        ["title-en", "title-ru"],
        ["desc-en", "desc-ru"],
        ["from-title-en", "from-title-ru"],
        ["to-title-en", "to-title-ru"],
        ["import-text-en", "import-text-ru"],
        ["log-title-en", "log-title-ru"],
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
        ["local-import-title-en", "local-import-title-ru"],
        ["local-rules-label-en", "local-rules-label-ru"],
        ["local-actions-label-en", "local-actions-label-ru"],
        ["import-action-local-btn-en", "import-action-local-btn-ru"],
        ["import-rule-local-btn-en", "import-rule-local-btn-ru"],
        ["tenant-export-hint-en", "tenant-export-hint-ru"],
        ["tenant-export-label-en", "tenant-export-label-ru"],
        ["tenant-import-label-en", "tenant-import-label-ru"],
        ["tenant-import-hint-en", "tenant-import-hint-ru"],
        ["import-actions-title-en", "import-actions-title-ru"],
        ["import-rules-title-en", "import-rules-title-ru"],
        ["import-action-btn-en", "import-action-btn-ru"],
        ["import-rule-btn-en", "import-rule-btn-ru"],
        ["download-action-json-btn-en", "download-action-json-btn-ru"],
        ["download-rule-json-btn-en", "download-rule-json-btn-ru"],
        ["download-local-action-json-btn-en", "download-local-action-json-btn-ru"],
        ["download-local-rule-json-btn-en", "download-local-rule-json-btn-ru"],
        ["import-action-local-btn-en", "import-action-local-btn-ru"],
        ["import-rule-local-btn-en", "import-rule-local-btn-ru"],
        ["source-app-label-en", "source-app-label-ru"],
        ["source-app-hint-en", "source-app-hint-ru"],
        ["import-app-button-en", "import-app-button-ru"],
        ["download-json-button-en", "download-json-button-ru"],
        ["reload-tenants-en", "reload-tenants-ru"],
        ["reload-local-exports-en", "reload-local-exports-ru"],
        ["print-apps-en", "print-apps-ru"],
        ["print-hosts-en", "print-hosts-ru"],
        ["print-tenant-hosts-en", "print-tenant-hosts-ru"],
        ["export-snapshots-en", "export-snapshots-ru"],
        ["export-rules-en", "export-rules-ru"],
        ["export-actions-en", "export-actions-ru"],
        ["export-global-lists-en", "export-global-lists-ru"],
        ["export-all-en", "export-all-ru"],
        ["print-title-en", "print-title-ru"],
        ["export-title-en", "export-title-ru"],
        // IP Management tab
        ["ip-title-en", "ip-title-ru"],
        ["ip-tenant-label-en", "ip-tenant-label-ru"],
        ["ip-tenant-hint-en", "ip-tenant-hint-ru"],
        ["ip-list-label-en", "ip-list-label-ru"],
        ["ip-list-hint-en", "ip-list-hint-ru"],
        ["create-list-title-en", "create-list-title-ru"],
        ["new-list-name-label-en", "new-list-name-label-ru"],
        ["new-list-type-label-en", "new-list-type-label-ru"],
        ["new-list-type-hint-en", "new-list-type-hint-ru"],
        ["new-list-force-label-en", "new-list-force-label-ru"],
        ["new-list-force-hint-en", "new-list-force-hint-ru"],
        ["ip-address-label-en", "ip-address-label-ru"],
        ["ip-address-hint-en", "ip-address-hint-ru"],
        ["ip-ttl-label-en", "ip-ttl-label-ru"],
        ["ip-result-placeholder-en", "ip-result-placeholder-ru"],
        ["main-result-placeholder-en", "main-result-placeholder-ru"],
        ["log-result-placeholder-en", "log-result-placeholder-ru"],
        ["log-display-title-en", "log-display-title-ru"],
        ["backup-title-en", "backup-title-ru"],
        ["backup-btn-en", "backup-btn-ru"],
        ["permanent-ip-title-en", "permanent-ip-title-ru"],
        // Policy Manager tab
        ["policy-title-en", "policy-title-ru"],
        ["policy-tenant-label-en", "policy-tenant-label-ru"],
        ["policy-tenant-hint-en", "policy-tenant-hint-ru"],
        ["rule-mod-title-en", "rule-mod-title-ru"],
        ["add-whitelist-label-en", "add-whitelist-label-ru"],
        ["add-whitelist-hint-en", "add-whitelist-hint-ru"],
        ["whitelist-name-label-en", "whitelist-name-label-ru"],
        ["whitelist-name-hint-en", "whitelist-name-hint-ru"],
        ["policy-result-placeholder-en", "policy-result-placeholder-ru"],
      ];
      ids.forEach(([en, ru]) => {
        const enEl = document.getElementById(en);
        const ruEl = document.getElementById(ru);
        if (enEl) enEl.classList.toggle("hidden", lang !== "en");
        if (ruEl) ruEl.classList.toggle("hidden", lang !== "ru");
      });

      // Update result placeholders
      const mainResult = document.getElementById("main-result");
      const logResult = document.getElementById("log-result");
      if (mainResult) {
        mainResult.innerHTML = lang === "ru"
          ? '<span id="main-result-placeholder-ru" class="">Готов</span>'
          : '<span id="main-result-placeholder-en" class="">Ready</span>';
      }
      if (logResult) {
        logResult.innerHTML = lang === "ru"
          ? '<span id="log-result-placeholder-ru" class="">Готов</span>'
          : '<span id="log-result-placeholder-en" class="">Ready</span>';
      }

      // Update language toggle button flag
      const langToggle = document.getElementById("lang-toggle");
      if (langToggle) {
        langToggle.textContent = lang === "ru" ? "🇷🇺" : "🇺🇸";
      }

      // Update language select in settings
      const langSelect = document.getElementById("setting-language");
      if (langSelect) langSelect.value = lang;

      populateTenantSelect("tenant-select", true);
      populateTenantSelect("import-tenant-select", true);
      populateTenantSelect("ip-tenant", true);
    }

    function toggleLanguage() {
      const newLang = currentLang === "ru" ? "en" : "ru";
      setLang(newLang);
      fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: newLang })
      }).catch(e => console.warn("Failed to save language", e));
    }

    function setTheme(theme) {
      currentTheme = theme;
      document.body.setAttribute("data-theme", theme);
      const themeSelect = document.getElementById("setting-theme");
      if (themeSelect) themeSelect.value = theme;
    }

    function toggleTheme() {
      const next = currentTheme === "light" ? "dark" : "light";
      setTheme(next);
      fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme: next })
      }).catch(e => console.warn("Failed to save theme", e));
    }

    function adjustLogSize() {
      const logEl = document.getElementById("log");
      if (!logEl) return;
      const rect = logEl.getBoundingClientRect();
      const availableHeight = window.innerHeight - rect.top - 16;
      const targetHeight = Math.max(240, availableHeight);
      const availableWidthPx = Math.max(360, window.innerWidth - rect.left - 16);
      logEl.style.height = `${targetHeight}px`;
      logEl.style.maxHeight = `${targetHeight}px`;
      logEl.style.maxWidth = `${availableWidthPx}px`;
    }

    window.addEventListener("resize", adjustLogSize);

    function log(msg) {
      const el = document.getElementById("log");
      const line = document.createElement("div");
      const now = new Date().toISOString();
      line.textContent = "[" + now + "] " + msg;
      el.appendChild(line);
      el.scrollTop = el.scrollHeight;
    }

    function formatSnapshotInfo(dateStr) {
      const parsed = new Date(dateStr);
      const formatted = Number.isNaN(parsed.getTime()) ? dateStr : parsed.toLocaleString();
      return currentLang === "ru" ? `снапшот: ${formatted}` : `snapshot: ${formatted}`;
    }

    async function loadSettings() {
      log("Loading settings...");
      const resp = await fetch("/api/settings");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      const data = await resp.json();
      currentLang = data.language || currentLang;
      currentTheme = data.theme || currentTheme;

      document.getElementById("setting-language").value = currentLang;
      document.getElementById("setting-theme").value = currentTheme;
      document.getElementById("setting-af-url").value = data.af_url || "";
      document.getElementById("setting-api-login").value = data.api_login || "";
      document.getElementById("setting-api-password").value = data.api_password || "";
      document.getElementById("setting-verify-ssl").checked = data.verify_ssl !== false;
      document.getElementById("setting-ldap-auth").checked = !!data.ldap_auth;
      document.getElementById("setting-snapshot-retention").value = data.snapshot_retention_days ?? 30;

      setLang(currentLang);
      setTheme(currentTheme);
    }

    function tenantOptionLabel(t) {
      return t.name || t.displayName || t.id;
    }

    function populateTenantSelect(selectId, includeAll = false) {
      const select = document.getElementById(selectId);
      if (!select) return;
      const previous = select.value;
      select.innerHTML = "";
      if (includeAll) {
        const optAll = document.createElement("option");
        optAll.value = "__all__";
        optAll.textContent = currentLang === "ru" ? "Все тенанты" : "All tenants";
        select.appendChild(optAll);
      }
      tenantsCache.forEach((t) => {
        const opt = document.createElement("option");
        opt.value = t.id;
        opt.textContent = tenantOptionLabel(t);
        select.appendChild(opt);
      });
      if (previous) select.value = previous;
      if (!select.value && select.options.length) select.selectedIndex = 0;
      
      if (selectId === "ip-tenant") {
        if (select.value === "__all__") {
          const listRow = document.getElementById("ip-list-row");
          if (listRow) listRow.style.display = "none";
        } else {
          const listRow = document.getElementById("ip-list-row");
          if (listRow) listRow.style.display = "flex";
          loadIpLists();
        }
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
          const val = document.getElementById("setting-snapshot-retention").value.trim();
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
      window.location.reload();
    }

    async function loadTenants() {
      log("Loading tenants...");
      const resp = await fetch("/api/tenants");
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        if (resp.status === 401 || data.error === "authentication_failed") {
          const msg = currentLang === "ru" 
            ? "Ошибка аутентификации! Проверьте логин/пароль в настройках." 
            : "Authentication failed! Please check your login/password in Settings.";
          showNotification(msg, "error");
          throw new Error("authentication_failed");
        }
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }
      const data = await resp.json();
      tenantsCache = data;
      log(`[loadTenants] tenantsCache: ${JSON.stringify(data.map(t => ({ id: t.id, name: t.name, displayName: t.displayName })))}`);
      populateTenantSelect("tenant-select", true);
      populateTenantSelect("import-tenant-select", true);
      populateTenantSelect("ip-tenant", true);
      populateTenantSelect("policy-tenant", true);
      loadApplicationsForSourceTenant();
      log("Loaded " + data.length + " tenants");
    }

    async function loadApplicationsForSourceTenant() {
      const sourceTenantId = document.getElementById("tenant-select").value;
      const appSelect = document.getElementById("source-application-select");
      if (!sourceTenantId || sourceTenantId === "__all__") {
        appSelect.innerHTML = '<option value="">— select source tenant first —</option>';
        return;
      }
      log("Loading applications for source tenant " + sourceTenantId);
      try {
        const resp = await fetch(`/api/tenants/${encodeURIComponent(sourceTenantId)}/applications`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const apps = await resp.json();
        appSelect.innerHTML = '<option value="">-- select application --</option>';
        if (apps.length === 0) {
          appSelect.innerHTML = '<option value="">— no applications found —</option>';
          log("No applications found for tenant " + sourceTenantId);
          return;
        }
        apps.forEach(app => {
          const opt = document.createElement("option");
          opt.value = app.id;
          opt.textContent = app.name || app.id;
          appSelect.appendChild(opt);
        });
        log(`Loaded ${apps.length} application(s) for source tenant`);
      } catch (err) {
        log("Failed to load applications: " + err);
        appSelect.innerHTML = '<option value="">— error loading applications —</option>';
      }
    }

    async function importApplicationToTarget() {
      const sourceTenantId = document.getElementById("tenant-select").value;
      const targetTenantId = document.getElementById("import-tenant-select").value;
      const applicationId = document.getElementById("source-application-select").value;
      if (!sourceTenantId || sourceTenantId === "__all__") {
        setImportResult("❌ " + (currentLang === "ru" ? "Выберите тенант-источник" : "Please select a specific source tenant"), "error");
        return;
      }
      if (!targetTenantId || targetTenantId === "__all__") {
        setImportResult("❌ " + (currentLang === "ru" ? "Выберите тенант-получатель" : "Please select a specific target tenant"), "error");
        return;
      }
      if (!applicationId) {
        setImportResult("❌ " + (currentLang === "ru" ? "Выберите приложение" : "Please select an application"), "error");
        return;
      }
      setImportResult("⏳ " + (currentLang === "ru" ? "Импорт приложения..." : "Importing application..."), "info");
      log(`Importing application ${applicationId} from ${sourceTenantId} to ${targetTenantId}...`);
      try {
        const resp = await fetch(`/api/tenants/${encodeURIComponent(targetTenantId)}/import_application`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source_tenant_id: sourceTenantId, application_id: applicationId })
        });
        const data = await resp.json();
        if (resp.ok) {
          log(`Import successful: ${JSON.stringify(data)}`);
          setImportResult("✅ " + (currentLang === "ru" ? "Приложение импортировано" : "Application imported"), "success");
          await loadTenants();
        } else {
          setImportResult("❌ " + (currentLang === "ru" ? "Ошибка импорта" : "Import failed") + ": " + JSON.stringify(data), "error");
          log(`Import failed: ${JSON.stringify(data)}`);
        }
      } catch (err) {
        setImportResult("❌ " + (currentLang === "ru" ? "Ошибка импорта" : "Import error") + ": " + err, "error");
        log("Import error: " + err);
      }
    }

    async function downloadMergedSnapshot() {
      const sourceTenantId = document.getElementById("tenant-select").value;
      const targetTenantId = document.getElementById("import-tenant-select").value;
      const applicationId = document.getElementById("source-application-select").value;
      if (!sourceTenantId || sourceTenantId === "__all__") {
        setImportResult("❌ " + (currentLang === "ru" ? "Выберите тенант-источник" : "Please select a specific source tenant"), "error");
        return;
      }
      if (!targetTenantId || targetTenantId === "__all__") {
        setImportResult("❌ " + (currentLang === "ru" ? "Выберите тенант-получатель" : "Please select a specific target tenant"), "error");
        return;
      }
      if (!applicationId) {
        setImportResult("❌ " + (currentLang === "ru" ? "Выберите приложение" : "Please select an application"), "error");
        return;
      }
      setImportResult("⏳ " + (currentLang === "ru" ? "Генерация снапшота..." : "Generating merged snapshot..."), "info");
      log(`Generating merged snapshot for tenant ${targetTenantId} with application ${applicationId} from ${sourceTenantId}...`);
      try {
        const resp = await fetch(`/api/tenants/${encodeURIComponent(targetTenantId)}/merge_application_json`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source_tenant_id: sourceTenantId, application_id: applicationId })
        });
        if (!resp.ok) {
          const text = await resp.text();
          setImportResult("❌ " + (currentLang === "ru" ? "Ошибка генерации" : "Failed to generate") + `: ${resp.status}`, "error");
          log(`Failed to generate merged snapshot: ${resp.status} ${text}`);
          return;
        }
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const contentDisposition = resp.headers.get('Content-Disposition');
        let filename = `merged_snapshot_${targetTenantId}.json`;
        if (contentDisposition) {
          const match = contentDisposition.match(/filename="?([^"]+)"?/);
          if (match) filename = match[1];
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        setImportResult("✅ " + (currentLang === "ru" ? "Снапшот загружен" : "Snapshot downloaded") + `: ${filename}`, "success");
        log(`Downloaded merged snapshot as ${filename}`);
      } catch (err) {
        setImportResult("❌ " + (currentLang === "ru" ? "Ошибка загрузки" : "Download error") + ": " + err, "error");
        log("Download error: " + err);
      }
    }

    function getSelectedExportTenantIds() {
      const select = document.getElementById("tenant-select");
      if (!select) return [];
      if (select.value === "__all__") return tenantsCache.map(t => String(t.id)).filter(Boolean);
      return select.value ? [select.value] : [];
    }

    function getImportTargetTenantIds() {
      const select = document.getElementById("import-tenant-select");
      if (!select) return [];
      if (select.value === "__all__") return tenantsCache.map(t => String(t.id)).filter(Boolean);
      return select.value ? [select.value] : [];
    }

    async function runSnapshots() {
      log("Running: fetch snapshots to RAM cache");
      setMainResult("⏳ Fetching snapshots...", "info");
      try {
        const resp = await fetch("/api/init/snapshots", { method: "POST" });
        const data = await resp.json();
        if (resp.ok) {
          const errors = data.errors || [];
          if (errors.length > 0) {
            const tenantNames = errors.map(e => e.tenant_name || e.tenant_id || "unknown").join(", ");
            const errorMsg = currentLang === "ru"
              ? `Ошибка доступа к снапшотам для ${errors.length} тенант(а/ов): ${tenantNames}. Проверьте права пользователя.`
              : `Snapshot access denied for ${errors.length} tenant(s): ${tenantNames}. Check user permissions.`;
            showNotification(errorMsg, "error");
            log("Snapshot errors: " + JSON.stringify(errors));
            errors.forEach(err => {
              const tenantInfo = err.tenant_name || err.tenant_id || "unknown";
              log(`[403] Tenant ${tenantInfo}: ${err.error}`);
            });
          }
          setMainResult("✅ " + (currentLang === "ru" ? "Снапшоты загружены в кэш" : "Snapshots cached") + (errors.length > 0 ? ` (${data.snapshots_cached}/${tenantsCache.length})` : ""), "success");
          snapshotSummaryCache = null;
          await loadTenants();
        } else {
          setMainResult("❌ " + (currentLang === "ru" ? "Ошибка загрузки" : "Fetch failed") + ": " + JSON.stringify(data), "error");
        }
        log("Snapshots result: " + JSON.stringify(data));
      } catch (err) {
        setMainResult("❌ " + (currentLang === "ru" ? "Ошибка" : "Error") + ": " + err, "error");
        log("Snapshots error: " + err);
      }
    }

    async function downloadBackup() {
      setMainResult("⏳ " + (currentLang === "ru" ? "Создание бэкапа..." : "Creating backup..."), "info");
      try {
        const timestamp = new Date().toISOString().slice(0, 19).replace(/[:.]/g, "-");
        const filename = timestamp + ".ptaf_backup.tar.gz";
        const a = document.createElement("a");
        a.href = "/api/backup";
        a.download = filename;
        a.target = "_blank";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => {
          setMainResult("✅ " + (currentLang === "ru" ? "Бэкап скачан" : "Backup downloaded"), "success");
        }, 1000);
      } catch (err) {
        setMainResult("❌ " + (currentLang === "ru" ? "Ошибка бэкапа" : "Backup error") + ": " + err, "error");
        log("Backup error: " + err);
      }
    }

    async function runRulesExport() {
      const tenantIds = getSelectedExportTenantIds();
      if (!tenantIds.length) { setMainResult("❌ " + (currentLang === "ru" ? "Тенант не выбран" : "No tenant selected"), "error"); return; }
      setMainResult("⏳ " + (currentLang === "ru" ? "Экспорт правил..." : "Exporting rules..."), "info");
      try {
        for (const tenantId of tenantIds) {
          log("Exporting rules for tenant " + tenantId);
          const resp = await fetch("/api/tenants/" + encodeURIComponent(tenantId) + "/rules/export", { method: "POST" });
          const data = await resp.json();
          log("Rules export result: " + JSON.stringify(data));
        }
        await loadLocalExports();
        setMainResult("✅ " + (currentLang === "ru" ? "Правила экспортированы" : "Rules exported"), "success");
      } catch (err) {
        setMainResult("❌ " + (currentLang === "ru" ? "Ошибка экспорта" : "Export failed") + ": " + err, "error");
        log("Rules export error: " + err);
      }
    }

    async function fetchSnapshotSummary(force = false) {
      if (!force && snapshotSummaryCache) return snapshotSummaryCache;
      log("Loading snapshot summary from RAM cache...");
      const resp = await fetch("/api/snapshots/summary");
      if (!resp.ok) {
        log("Failed to read snapshot summary: " + resp.statusText);
        return null;
      }
      const data = await resp.json();
      snapshotSummaryCache = data;
      if (!data.snapshot_files) log("No snapshots found in cache");
      else log("Snapshot summary loaded from " + data.snapshot_files + " tenant(s)");
      return data;
    }

    function logItemsWithPrefix(items, prefix, emptyMessage) {
      if (!items || !items.length) { log(emptyMessage); return; }
      items.forEach((item) => {
        const text = typeof item === "string" ? item : JSON.stringify(item);
        log(prefix + text);
      });
    }

    async function logSnapshotApplications() {
      setLogResult("⏳ " + (currentLang === "ru" ? "Загрузка приложений..." : "Loading applications..."), "info");
      try {
        const summary = await fetchSnapshotSummary();
        if (!summary) {
          setLogResult("❌ " + (currentLang === "ru" ? "Ошибка загрузки" : "Failed to load"), "error");
          return;
        }
        logItemsWithPrefix(summary.applications || [], "[apps] ", currentLang === "ru" ? "Нет приложений в снапшотах" : "No applications found in snapshots");
        setLogResult("✅ " + (currentLang === "ru" ? "Приложения выведены в лог" : "Applications printed to log"), "success");
      } catch (err) {
        setLogResult("❌ " + (currentLang === "ru" ? "Ошибка" : "Error") + ": " + err, "error");
        log("Log applications error: " + err);
      }
    }

    async function logSnapshotHosts() {
      setLogResult("⏳ " + (currentLang === "ru" ? "Загрузка хостов..." : "Loading hosts..."), "info");
      try {
        const summary = await fetchSnapshotSummary();
        if (!summary) {
          setLogResult("❌ " + (currentLang === "ru" ? "Ошибка загрузки" : "Failed to load"), "error");
          return;
        }
        logItemsWithPrefix(summary.hosts || [], "[host] ", currentLang === "ru" ? "Нет хостов в снапшотах" : "No hosts found in snapshots");
        setLogResult("✅ " + (currentLang === "ru" ? "Хосты выведены в лог" : "Hosts printed to log"), "success");
      } catch (err) {
        setLogResult("❌ " + (currentLang === "ru" ? "Ошибка" : "Error") + ": " + err, "error");
        log("Log hosts error: " + err);
      }
    }

    async function logSnapshotTenantHosts() {
      setLogResult("⏳ " + (currentLang === "ru" ? "Загрузка тенантов и хостов..." : "Loading tenants and hosts..."), "info");
      try {
        const summary = await fetchSnapshotSummary();
        if (!summary) {
          setLogResult("❌ " + (currentLang === "ru" ? "Ошибка загрузки" : "Failed to load"), "error");
          return;
        }
        const entries = Array.isArray(summary.tenant_hosts) ? summary.tenant_hosts : [];
        if (!entries.length) {
          log(currentLang === "ru" ? "Нет данных по тенантам в снапшотах" : "No tenant data found in snapshots");
          setLogResult("⚠️ " + (currentLang === "ru" ? "Нет данных" : "No data found"), "info");
          return;
        }
        entries.forEach((entry) => {
          const hosts = Array.isArray(entry.hosts) ? entry.hosts.join(",") : "";
          const name = entry.tenant_name || "unknown";
          log(`[tenant] ${name}: ${hosts}`);
        });
        setLogResult("✅ " + (currentLang === "ru" ? "Тенанты и хосты выведены в лог" : "Tenants and hosts printed to log"), "success");
      } catch (err) {
        setLogResult("❌ " + (currentLang === "ru" ? "Ошибка" : "Error") + ": " + err, "error");
        log("Log tenant hosts error: " + err);
      }
    }

    async function runActionsExport() {
      const tenantIds = getSelectedExportTenantIds();
      if (!tenantIds.length) { setMainResult("❌ " + (currentLang === "ru" ? "Тенант не выбран" : "No tenant selected"), "error"); return; }
      setMainResult("⏳ " + (currentLang === "ru" ? "Экспорт действий..." : "Exporting actions..."), "info");
      try {
        for (const tenantId of tenantIds) {
          log("Exporting actions for tenant " + tenantId);
          const resp = await fetch("/api/tenants/" + encodeURIComponent(tenantId) + "/actions/export", { method: "POST" });
          const data = await resp.json();
          log("Actions export result: " + JSON.stringify(data));
        }
        await loadLocalExports();
        setMainResult("✅ " + (currentLang === "ru" ? "Действия экспортированы" : "Actions exported"), "success");
      } catch (err) {
        setMainResult("❌ " + (currentLang === "ru" ? "Ошибка экспорта" : "Export failed") + ": " + err, "error");
        log("Actions export error: " + err);
      }
    }

    async function runGlobalListsExport() {
      const tenantIds = getSelectedExportTenantIds();
      if (!tenantIds.length) { setMainResult("❌ " + (currentLang === "ru" ? "Тенант не выбран" : "No tenant selected"), "error"); return; }
      setMainResult("⏳ " + (currentLang === "ru" ? "Экспорт глобальных списков..." : "Exporting global lists..."), "info");
      try {
        for (const tenantId of tenantIds) {
          log("Exporting global lists for tenant " + tenantId);
          const resp = await fetch("/api/tenants/" + encodeURIComponent(tenantId) + "/global_lists/export", { method: "POST" });
          const data = await resp.json();
          log("Global lists export result: " + JSON.stringify(data));
        }
        await loadLocalExports();
        setMainResult("✅ " + (currentLang === "ru" ? "Глобальные списки экспортированы" : "Global lists exported"), "success");
      } catch (err) {
        setMainResult("❌ " + (currentLang === "ru" ? "Ошибка экспорта" : "Export failed") + ": " + err, "error");
        log("Global lists export error: " + err);
      }
    }

    async function exportAll() {
      log("🚀 Starting full export (snapshots, rules, actions, global lists)...");
      setMainResult("⏳ " + (currentLang === "ru" ? "Запуск полного экспорта..." : "Starting full export..."), "info");
      try {
        await runSnapshots();
        await runRulesExport();
        await runActionsExport();
        await runGlobalListsExport();
        setMainResult("✅ " + (currentLang === "ru" ? "Полный экспорт завершен" : "Full export completed"), "success");
        log("✅ Full export completed.");
      } catch (err) {
        setMainResult("❌ " + (currentLang === "ru" ? "Ошибка экспорта" : "Export failed") + ": " + err, "error");
        log("Export all error: " + err);
      }
    }

    async function importRule() { await importJsonTo("/rules/import", "rule-file-input"); }
    async function importAction() { await importJsonTo("/actions/import", "action-file-input"); }

    async function downloadRuleJson() {
      const fileInput = document.getElementById("rule-file-input");
      if (!fileInput || !fileInput.files.length) { setImportResult("❌ " + (currentLang === "ru" ? "Файл не выбран" : "No file selected"), "error"); return; }
      const file = fileInput.files[0];
      const url = URL.createObjectURL(file);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setImportResult("✅ " + (currentLang === "ru" ? "Файл правил загружен" : "Rule file downloaded"), "success");
    }

    async function downloadActionJson() {
      const fileInput = document.getElementById("action-file-input");
      if (!fileInput || !fileInput.files.length) { setImportResult("❌ " + (currentLang === "ru" ? "Файл не выбран" : "No file selected"), "error"); return; }
      const file = fileInput.files[0];
      const url = URL.createObjectURL(file);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setImportResult("✅ " + (currentLang === "ru" ? "Файл действий загружен" : "Action file downloaded"), "success");
    }

    function setImportResult(html, type = "info") {
      setMainResult(html, type);
    }

    function localData(kind) { return kind === "rule" ? localRuleExports : localActionExports; }

    function updateLocalSelects(kind) {
      const filesSelect = document.getElementById(`local-${kind}s-file`);
      filesSelect.innerHTML = "";
      updateLocalFiles(kind);
    }

    function updateLocalFiles(kind) {
      const filesSelect = document.getElementById(`local-${kind}s-file`);
      filesSelect.innerHTML = "";
      
      if (kind === "rule") {
        const exportTenantId = document.getElementById("tenant-select").value;
        log(`[updateLocalFiles] exportTenantId=${exportTenantId}, snapshotUserRules count=${snapshotUserRules.length}`);
        let rulesToDisplay = [];
        
        if (exportTenantId === "__all__") {
          snapshotUserRules.forEach((entry) => {
            log(`[updateLocalFiles] entry.tenant_name=${entry.tenant_name}, tenant_id=${entry.tenant_id}, rules count=${entry.user_rules.length}`);
            entry.user_rules.forEach((rule) => {
              rulesToDisplay.push({ name: rule.name, tenant: entry.tenant_name });
            });
          });
        } else {
          const matchingEntry = snapshotUserRules.find(entry => entry.tenant_id === exportTenantId);
          log(`[updateLocalFiles] Looking for tenant_id=${exportTenantId}, found matchingEntry=${!!matchingEntry}`);
          if (matchingEntry) {
            log(`[updateLocalFiles] Found ${matchingEntry.user_rules.length} rules for tenant ${exportTenantId}`);
            matchingEntry.user_rules.forEach((rule) => {
              rulesToDisplay.push({ name: rule.name, tenant: matchingEntry.tenant_name });
            });
          } else {
            log(`[updateLocalFiles] No matching entry found. Available tenant_ids: ${snapshotUserRules.map(e => e.tenant_id).join(", ")}`);
          }
        }
        
        log(`[updateLocalFiles] rulesToDisplay count=${rulesToDisplay.length}`);
        rulesToDisplay.forEach((rule) => {
          const opt = document.createElement("option");
          opt.value = rule.name;
          opt.textContent = rule.name;
          filesSelect.appendChild(opt);
        });
      } else {
        const exportTenantId = document.getElementById("tenant-select").value;
        log(`[updateLocalFiles action] exportTenantId=${exportTenantId}, localActionExports count=${localActionExports.length}`);
        let actionsToDisplay = [];
        
        if (exportTenantId === "__all__") {
          localActionExports.forEach((entry) => {
            log(`[updateLocalFiles action] entry.tenant_name=${entry.tenant_name}, tenant_id=${entry.tenant_id}, files count=${entry.files.length}`);
            entry.files.forEach((item) => {
              actionsToDisplay.push({
                filename: typeof item === "string" ? item : item.filename,
                label: typeof item === "string" ? item : item.display_name || item.filename,
              });
            });
          });
        } else {
          const matchingEntry = localActionExports.find(entry => entry.tenant_id === exportTenantId);
          log(`[updateLocalFiles action] Looking for tenant_id=${exportTenantId}, found matchingEntry=${!!matchingEntry}`);
          if (matchingEntry) {
            log(`[updateLocalFiles action] Found ${matchingEntry.files.length} actions for tenant ${exportTenantId}`);
            matchingEntry.files.forEach((item) => {
              actionsToDisplay.push({
                filename: typeof item === "string" ? item : item.filename,
                label: typeof item === "string" ? item : item.display_name || item.filename,
              });
            });
          } else {
            log(`[updateLocalFiles action] No matching entry found. Available tenant_ids: ${localActionExports.map(e => e.tenant_id).join(", ")}`);
          }
        }
        
        log(`[updateLocalFiles action] actionsToDisplay count=${actionsToDisplay.length}`);
        actionsToDisplay.forEach((action) => {
          const textLabel = action.filename && action.label && action.filename !== action.label ? `${action.label} (${action.filename})` : action.label || action.filename;
          const opt = document.createElement("option");
          opt.value = action.filename;
          opt.textContent = textLabel || action.filename || "";
          filesSelect.appendChild(opt);
        });
      }
    }

    async function loadLocalExports() {
      // Сначала загружаем снапшоты в RAM
      log("Fetching snapshots to RAM cache...");
      try {
        const resp = await fetch("/api/init/snapshots", { method: "POST" });
        if (resp.ok) {
          const data = await resp.json();
          const errors = data.errors || [];
          if (errors.length > 0) {
            const tenantNames = errors.map(e => e.tenant_name || e.tenant_id || "unknown").join(", ");
            const errorMsg = currentLang === "ru"
              ? `Нет доступа к снапшотам для ${errors.length} тенант(а/ов): ${tenantNames}. Проверьте права пользователя.`
              : `Snapshot access denied for ${errors.length} tenant(s): ${tenantNames}. Check user permissions.`;
            showNotification(errorMsg, "error");
            log("Snapshot errors: " + JSON.stringify(errors));
            errors.forEach(err => {
              const tenantInfo = err.tenant_name || err.tenant_id || "unknown";
              log(`[403] Tenant ${tenantInfo}: ${err.error}`);
            });
          }
        }
      } catch (err) {
        log("Failed to fetch snapshots: " + err);
      }
      
      const [localResp, snapshotResp] = await Promise.all([
        fetch("/api/local-imports"),
        fetch("/api/snapshots/user-rules")
      ]);
      if (!localResp.ok) {
        log("Failed to load local exports: " + localResp.statusText);
        return;
      }
      if (!snapshotResp.ok) {
        log("Failed to load snapshot user rules: " + snapshotResp.statusText);
        return;
      }
      const localData = await localResp.json();
      const snapshotData = await snapshotResp.json();
      localRuleExports = localData.rules || [];
      localActionExports = localData.actions || [];
      snapshotUserRules = snapshotData || [];
      log(`[loadLocalExports] snapshotUserRules: ${JSON.stringify(snapshotUserRules)}`);
      updateLocalSelects("rule");
      updateLocalSelects("action");
      log(`Loaded local exports: ${localRuleExports.length} rule tenants, ${localActionExports.length} action tenants, ${snapshotUserRules.length} tenants with user rules`);
    }

    async function importRuleFromLocal() { await importFromLocal("rule"); }
    async function importActionFromLocal() { await importFromLocal("action"); }

    async function downloadLocalRuleJson() {
      const fileSelect = document.getElementById("local-rules-file");
      const ruleName = fileSelect.value;
      if (!ruleName) { setImportResult("❌ " + (currentLang === "ru" ? "Выберите правило" : "Select rule first"), "error"); return; }
      const sourceTenant = findTenantByRuleName(ruleName);
      if (!sourceTenant) { setImportResult("❌ " + (currentLang === "ru" ? "Тенант не найден" : "Tenant not found"), "error"); return; }
      try {
        const resp = await fetch(`/api/local-imports/rules/${encodeURIComponent(sourceTenant)}/${encodeURIComponent(ruleName)}`);
        if (!resp.ok) {
          const data = await resp.json();
          setImportResult("❌ " + (currentLang === "ru" ? "Ошибка загрузки" : "Download failed") + ": " + JSON.stringify(data), "error");
          return;
        }
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${ruleName}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        setImportResult("✅ " + (currentLang === "ru" ? "Правило загружено" : "Rule downloaded"), "success");
      } catch (err) {
        setImportResult("❌ " + (currentLang === "ru" ? "Ошибка загрузки" : "Download error") + ": " + err, "error");
        log("Download local rule error: " + err);
      }
    }

    async function downloadLocalActionJson() {
      const fileSelect = document.getElementById("local-actions-file");
      const filename = fileSelect.value;
      if (!filename) { setImportResult("❌ " + (currentLang === "ru" ? "Выберите действие" : "Select action first"), "error"); return; }
      const sourceTenant = findTenantByActionFilename(filename);
      if (!sourceTenant) { setImportResult("❌ " + (currentLang === "ru" ? "Тенант не найден" : "Tenant not found"), "error"); return; }
      try {
        const resp = await fetch(`/api/local-imports/actions/${encodeURIComponent(sourceTenant)}/${encodeURIComponent(filename)}`);
        if (!resp.ok) {
          const data = await resp.json();
          setImportResult("❌ " + (currentLang === "ru" ? "Ошибка загрузки" : "Download failed") + ": " + JSON.stringify(data), "error");
          return;
        }
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        setImportResult("✅ " + (currentLang === "ru" ? "Действие загружено" : "Action downloaded"), "success");
      } catch (err) {
        setImportResult("❌ " + (currentLang === "ru" ? "Ошибка загрузки" : "Download error") + ": " + err, "error");
        log("Download local action error: " + err);
      }
    }

    function findTenantByRuleName(ruleName) {
      for (const entry of snapshotUserRules) {
        if (entry.user_rules.some(r => r.name === ruleName)) {
          return entry.tenant_name;
        }
      }
      return null;
    }

    function findTenantByActionFilename(filename) {
      for (const entry of localActionExports) {
        if (entry.files.some(f => (typeof f === "string" ? f : f.filename) === filename)) {
          return entry.tenant_name;
        }
      }
      return null;
    }

    async function importFromLocal(kind) {
      const tenantIds = getImportTargetTenantIds();
      if (!tenantIds.length) { setImportResult("❌ " + (currentLang === "ru" ? "Тенант не выбран" : "No target tenant selected"), "error"); return; }
      const fileSelect = document.getElementById(`local-${kind}s-file`);
      const selectedValue = fileSelect.value;
      if (!selectedValue) { setImportResult("❌ " + (currentLang === "ru" ? "Выберите файл" : "Select file first"), "error"); return; }
      
      let sourceTenant;
      if (kind === "rule") {
        sourceTenant = findTenantByRuleName(selectedValue);
      } else {
        sourceTenant = findTenantByActionFilename(selectedValue);
      }
      
      if (!sourceTenant) { setImportResult("❌ " + (currentLang === "ru" ? "Тенант-источник не найден" : "Source tenant not found"), "error"); return; }
      
      if (kind === "rule") {
        setImportResult("⏳ " + (currentLang === "ru" ? "Импорт правила из снапшота..." : "Importing rule from snapshot..."), "info");
        try {
          for (const tenantId of tenantIds) {
            const ruleName = selectedValue;
            log(`Importing user rule "${ruleName}" from tenant ${sourceTenant} to tenant ${tenantId}`);
            const resp = await fetch(`/api/tenants/${encodeURIComponent(tenantId)}/rules/import/from-snapshot`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ source_tenant: sourceTenant, rule_name: ruleName }),
            });
            const data = await resp.json();
            if (!resp.ok) {
              setImportResult("❌ " + (currentLang === "ru" ? "Ошибка импорта" : "Import failed") + ": " + JSON.stringify(data), "error");
              log(`Import result for ${tenantId}: ` + JSON.stringify(data));
              return;
            }
            log(`Import result for ${tenantId}: ` + JSON.stringify(data));
          }
          setImportResult("✅ " + (currentLang === "ru" ? "Импорт завершен" : "Import completed"), "success");
        } catch (err) {
          setImportResult("❌ " + (currentLang === "ru" ? "Ошибка импорта" : "Import error") + ": " + err, "error");
          log("Import from snapshot error: " + err);
        }
      } else {
        const filename = selectedValue;
        const path = "/actions/import/local";
        setImportResult("⏳ " + (currentLang === "ru" ? "Импорт из локального файла..." : "Importing from local file..."), "info");
        try {
          for (const tenantId of tenantIds) {
            log(`Importing ${kind} from local export ${filename} (source ${sourceTenant}) to tenant ${tenantId}`);
            const resp = await fetch(`/api/tenants/${encodeURIComponent(tenantId)}${path}`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ source_tenant: sourceTenant, filename: filename }),
            });
            const data = await resp.json();
            if (!resp.ok) {
              setImportResult("❌ " + (currentLang === "ru" ? "Ошибка импорта" : "Import failed") + ": " + JSON.stringify(data), "error");
              log(`Import result for ${tenantId}: ` + JSON.stringify(data));
              return;
            }
            log(`Import result for ${tenantId}: ` + JSON.stringify(data));
          }
          setImportResult("✅ " + (currentLang === "ru" ? "Импорт завершен" : "Import completed"), "success");
        } catch (err) {
          setImportResult("❌ " + (currentLang === "ru" ? "Ошибка импорта" : "Import error") + ": " + err, "error");
          log("Import from local error: " + err);
        }
      }
    }

    async function importJsonTo(path, fileInputId) {
      const tenantIds = getImportTargetTenantIds();
      if (!tenantIds.length) { setImportResult("❌ " + (currentLang === "ru" ? "Тенант не выбран" : "No target tenant selected"), "error"); return; }
      const fileInput = document.getElementById(fileInputId);
      if (!fileInput || !fileInput.files.length) { setImportResult("❌ " + (currentLang === "ru" ? "Файл не выбран" : "No file selected"), "error"); return; }
      const file = fileInput.files[0];
      const form = new FormData();
      form.append("file", file);
      setImportResult("⏳ " + (currentLang === "ru" ? "Импорт файла..." : "Importing file..."), "info");
      try {
        for (const tenantId of tenantIds) {
          log(`Uploading ${file.name} to ${path} for tenant ${tenantId}`);
          const resp = await fetch("/api/tenants/" + encodeURIComponent(tenantId) + path, { method: "POST", body: form });
          const data = await resp.json();
          if (!resp.ok) {
            setImportResult("❌ " + (currentLang === "ru" ? "Ошибка импорта" : "Import failed") + ": " + JSON.stringify(data), "error");
            log(`Import result for ${tenantId}: ` + JSON.stringify(data));
            return;
          }
          log(`Import result for ${tenantId}: ` + JSON.stringify(data));
        }
        setImportResult("✅ " + (currentLang === "ru" ? "Импорт завершен" : "Import completed"), "success");
      } catch (err) {
        setImportResult("❌ " + (currentLang === "ru" ? "Ошибка импорта" : "Import error") + ": " + err, "error");
        log("Import JSON error: " + err);
      }
    }

    // ========== IP Management Functions ==========
    
    function onIpTenantChange() {
        const tenantId = document.getElementById("ip-tenant").value;
        const listRow = document.getElementById("ip-list-row");
        
        if (tenantId === "__all__") {
            listRow.style.display = "none";
        } else {
            listRow.style.display = "flex";
            loadIpLists();
        }
        clearIpResult();
    }

    async function loadIpLists() {
        const tenantId = document.getElementById("ip-tenant").value;
        const select = document.getElementById("ip-list");
        const ttlRow = document.getElementById("ip-ttl-row");
        
        if (!tenantId || tenantId === "__all__") {
            select.innerHTML = '<option value="">-- select tenant first --</option>';
            return;
        }
        
        select.innerHTML = '<option value="">-- loading --</option>';
        
        try {
            const resp = await fetch(`/api/tenants/${encodeURIComponent(tenantId)}/global_lists`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const lists = await resp.json();
            currentIpTenantLists = lists;
            
            select.innerHTML = '<option value="">-- select list --</option>';
            if (lists.length === 0) {
                select.innerHTML = '<option value="">— no global lists —</option>';
                return;
            }
            
            lists.forEach(lst => {
                const opt = document.createElement("option");
                opt.value = lst.id;
                const typeLabel = lst.type === "STATIC" ? "(STATIC)" : "(DYNAMIC)";
                opt.textContent = `${lst.name || lst.id} ${typeLabel}`;
                opt.dataset.type = lst.type || "DYNAMIC";
                select.appendChild(opt);
            });
            
            onIpListChange();
        } catch (err) {
            log("Failed to load global lists: " + err);
            select.innerHTML = '<option value="">— error —</option>';
        }
    }
    
    function onIpListChange() {
        const select = document.getElementById("ip-list");
        const ttlRow = document.getElementById("ip-ttl-row");
        const selectedOpt = select.options[select.selectedIndex];
        const listType = selectedOpt.dataset.type || "DYNAMIC";
        
        if (listType === "STATIC") {
            ttlRow.style.display = "none";
        } else {
            ttlRow.style.display = "flex";
        }
    }
    
    function onNewListTypeChange() {
        const listType = document.getElementById("new-list-type").value;
        const fileRow = document.getElementById("new-list-file-row");
        
        if (listType === "STATIC") {
            fileRow.style.display = "flex";
        } else {
            fileRow.style.display = "none";
        }
    }
    
    document.addEventListener("DOMContentLoaded", function() {
        const typeSelect = document.getElementById("new-list-type");
        if (typeSelect) {
            typeSelect.addEventListener("change", onNewListTypeChange);
            onNewListTypeChange();
        }
    });

    async function createGlobalList() {
        const tenantId = document.getElementById("ip-tenant").value;
        const name = document.getElementById("new-list-name").value.trim();
        const listType = document.getElementById("new-list-type").value;
        const description = document.getElementById("new-list-description").value.trim();
        const fileContent = document.getElementById("new-list-file").value.trim();
        const forceOverwrite = document.getElementById("new-list-force-overwrite").checked;
        
        if (!tenantId) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите тенант" : "Select tenant"}</span>`, true);
            return;
        }
        
        if (!name) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Введите название списка" : "Enter list name"}</span>`, true);
            return;
        }
        
        if (listType === "STATIC" && !fileContent) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Введите содержимое файла для STATIC списка" : "Enter file content for STATIC list"}</span>`, true);
            return;
        }
        
        setIpResult(`<span>${currentLang === "ru" ? "Создание списка..." : "Creating list..."}</span>`);
        
        try {
            const formData = new FormData();
            formData.append("tenant_id", tenantId);
            formData.append("name", name);
            formData.append("type", listType);
            if (description) {
                formData.append("description", description);
            }
            if (fileContent) {
                const blob = new Blob([fileContent], { type: "text/plain" });
                formData.append("file", blob, "global_list.txt");
            }
            formData.append("force_overwrite", forceOverwrite.toString());
            
            const resp = await fetch("/api/global_lists/create", {
                method: "POST",
                body: formData,
            });
            
            const data = await resp.json();
            
            if (resp.ok) {
                let html = `<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "Результат создания списка" : "List creation result"}:</span><br/>`;
                
                if (data.results && Array.isArray(data.results)) {
                    const successCount = data.summary?.success || 0;
                    const totalCount = data.summary?.total || data.results.length;
                    const existsCount = data.results.filter(r => r.status === "exists").length;
                    const overwrittenCount = data.results.filter(r => r.status === "overwritten").length;
                    const createdCount = data.results.filter(r => r.status === "created").length;
                    const failedCount = data.summary?.failed || 0;
                    
                    html += `<b>${currentLang === "ru" ? "Сводка" : "Summary"}:</b> `;
                    html += `${currentLang === "ru" ? "Создано" : "Created"}: ${createdCount}, `;
                    html += `${currentLang === "ru" ? "Перезаписано" : "Overwritten"}: ${overwrittenCount}, `;
                    html += `${currentLang === "ru" ? "Существует" : "Exists"}: ${existsCount}, `;
                    html += `${currentLang === "ru" ? "Ошибка" : "Failed"}: ${failedCount}<br/>`;
                    
                    data.results.forEach(r => {
                        const statusIcon = r.status === "created" ? "✅" : r.status === "overwritten" ? "🔄" : r.status === "exists" ? "⚠️" : r.status === "error" ? "❌" : "•";
                        let statusText = r.status === "created" ? (currentLang === "ru" ? "создан" : "created") : r.status === "overwritten" ? (currentLang === "ru" ? "перезаписан" : "overwritten") : r.status === "exists" ? (currentLang === "ru" ? "существует" : "exists") : r.error || "";
                        
                        if (r.apply_status === "applied") {
                            statusText += ` <span style="color: #27ae60;">✔ ${currentLang === "ru" ? "применен" : "applied"}</span>`;
                        } else if (r.apply_status === "apply_failed") {
                            statusText += ` <span style="color: #e74c3c;">✖ ${currentLang === "ru" ? "НЕ применен" : "NOT applied"}: ${r.apply_message}</span>`;
                        }
                        
                        html += `${statusIcon} <b>${r.tenant_name || r.tenant_id}</b>: ${statusText}<br/>`;
                    });
                } else {
                    const statusIcon = data.status === "created" ? "✅" : data.status === "overwritten" ? "🔄" : data.status === "exists" ? "⚠️" : "•";
                    let statusText = data.status === "created" ? (currentLang === "ru" ? "создан" : "created") : data.status === "overwritten" ? (currentLang === "ru" ? "перезаписан" : "overwritten") : data.status === "exists" ? (currentLang === "ru" ? "существует (не перезаписан)" : "exists (not overwritten)") : data.message || data.error || "";
                    
                    if (data.apply_status === "applied") {
                        statusText += ` <span style="color: #27ae60;">✔ ${currentLang === "ru" ? "применен" : "applied"}</span>`;
                    } else if (data.apply_status === "apply_failed") {
                        statusText += ` <span style="color: #e74c3c;">✖ ${currentLang === "ru" ? "НЕ применен" : "NOT applied"}: ${data.apply_message}</span>`;
                    }
                    
                    html += `${statusIcon} <b>${name}</b> [${listType}]: ${statusText}`;
                }
                
                setIpResult(html);
                
                if (!forceOverwrite) {
                    document.getElementById("new-list-name").value = "";
                    document.getElementById("new-list-description").value = "";
                    document.getElementById("new-list-file").value = "";
                }
                loadIpLists();
            } else {
                setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Ошибка" : "Error"}: ${data.error || JSON.stringify(data)}</span>`, true);
            }
        } catch (err) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Ошибка" : "Error"}: ${err}</span>`, true);
            log("Create list error: " + err);
        }
    }

    function clearIpResult() {
        const resultDiv = document.getElementById("ip-result");
        resultDiv.className = "result-box info";
        if (currentLang === "ru") {
            resultDiv.innerHTML = '<span id="ip-result-placeholder-ru" class="">Готов</span>';
        } else {
            resultDiv.innerHTML = '<span id="ip-result-placeholder-en" class="">Ready</span>';
        }
    }

    function setIpResult(html, isError = false) {
        const resultDiv = document.getElementById("ip-result");
        resultDiv.className = "result-box" + (isError ? " error" : " success");
        resultDiv.innerHTML = html;
    }

    function setMainResult(html, type = "info") {
        const resultDiv = document.getElementById("main-result");
        if (!resultDiv) return;
        resultDiv.className = "result-box " + type;
        resultDiv.innerHTML = html;
    }

    function setLogResult(html, type = "info") {
        const resultDiv = document.getElementById("log-result");
        if (!resultDiv) return;
        resultDiv.className = "result-box " + type;
        resultDiv.innerHTML = html;
    }

    async function addIp() {
        const tenantId = document.getElementById("ip-tenant").value;
        const listId = document.getElementById("ip-list").value;
        const ipsRaw = document.getElementById("ip-address").value;
        const ttl = parseInt(document.getElementById("ip-ttl").value, 10);
        
        if (!tenantId) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите тенант" : "Select tenant"}</span>`, true);
            return;
        }
        
        if (tenantId !== "__all__" && !listId) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите глобальный список" : "Select global list"}</span>`, true);
            return;
        }
        
        if (!ipsRaw.trim()) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Введите IP адрес(а)" : "Enter IP address(es)"}</span>`, true);
            return;
        }
        
        const items = ipsRaw.split(/[ ,;]+/).filter(s => s.trim().length > 0);
        
        setIpResult(`<span>${currentLang === "ru" ? "Добавление IP..." : "Adding IP..."}</span>`);
        
        try {
            const resp = await fetch("/api/global_lists/add_item", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tenant_id: tenantId, list_id: listId, items, ttl }),
            });
            const data = await resp.json();
            
            if (tenantId === "__all__") {
                const results = data.results || [];
                const successCount = results.filter(r => r.status === "OK" || !r.error).length;
                const failCount = results.filter(r => r.error).length;
                setIpResult(`<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "Добавлено" : "Added"} ${successCount}/${results.length} ${currentLang === "ru" ? "тенантов" : "tenants"}${failCount > 0 ? ` (${failCount} ${currentLang === "ru" ? "ошибок" : "errors"})` : ""}</span>`);
            } else {
                const listType = data.list_type || "DYNAMIC";
                let msg = `<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "IP добавлен" : "IP added"}`;
                if (data.already_exist && data.already_exist.length > 0) {
                    msg += ` (${currentLang === "ru" ? "уже существуют" : "already exist"}: ${data.already_exist.join(", ")})`;
                }
                if (data.added !== undefined) {
                    msg += ` (${currentLang === "ru" ? "добавлено" : "added"}: ${data.added})`;
                }
                msg += ` [${listType}]</span>`;
                setIpResult(msg);
            }
        } catch (err) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Ошибка" : "Error"}: ${err}</span>`, true);
        }
    }

    async function removeIp() {
        const tenantId = document.getElementById("ip-tenant").value;
        const listId = document.getElementById("ip-list").value;
        const ipsRaw = document.getElementById("ip-address").value;
        
        if (!tenantId) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите тенант" : "Select tenant"}</span>`, true);
            return;
        }
        
        if (tenantId !== "__all__" && !listId) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите глобальный список" : "Select global list"}</span>`, true);
            return;
        }
        
        if (!ipsRaw.trim()) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Введите IP адрес(а)" : "Enter IP address(es)"}</span>`, true);
            return;
        }
        
        const items = ipsRaw.split(/[ ,;]+/).filter(s => s.trim().length > 0);
        
        setIpResult(`<span>${currentLang === "ru" ? "Удаление IP..." : "Removing IP..."}</span>`);
        
        try {
            const resp = await fetch("/api/global_lists/remove_item", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tenant_id: tenantId, list_id: listId, items }),
            });
            const data = await resp.json();
            
            if (tenantId === "__all__") {
                const results = data.results || [];
                const successCount = results.filter(r => r.status === "OK" || !r.error).length;
                setIpResult(`<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "Удалено" : "Removed"} (${successCount}/${results.length} ${currentLang === "ru" ? "тенантов" : "tenants"})</span>`);
            } else {
                const listType = data.list_type || "DYNAMIC";
                let msg = `<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "IP удален" : "IP removed"}`;
                if (data.removed && data.removed.length > 0) {
                    msg += ` (${currentLang === "ru" ? "удалено" : "removed"}: ${data.removed.join(", ")})`;
                }
                if (data.not_found && data.not_found.length > 0) {
                    msg += ` (${currentLang === "ru" ? "не найдены" : "not found"}: ${data.not_found.join(", ")})`;
                }
                msg += ` [${listType}]</span>`;
                setIpResult(msg);
            }
        } catch (err) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Ошибка" : "Error"}: ${err}</span>`, true);
        }
    }

    async function checkIp() {
        const tenantId = document.getElementById("ip-tenant").value;
        const ip = document.getElementById("ip-address").value.trim();
        
        if (!ip) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Введите IP адрес для проверки" : "Enter IP address to check"}</span>`, true);
            return;
        }
        
        if (!tenantId) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите тенант" : "Select tenant"}</span>`, true);
            return;
        }
        
        setIpResult(`<span>${currentLang === "ru" ? "Проверка IP..." : "Checking IP..."}</span>`);
        
        let listId = null;
        if (tenantId !== "__all__") {
            listId = document.getElementById("ip-list").value;
            if (!listId) {
                setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите глобальный список" : "Select global list"}</span>`, true);
                return;
            }
        }
        
        try {
            const resp = await fetch("/api/global_lists/check_ip", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tenant_id: tenantId, list_id: listId, ip: ip }),
            });
            
            const data = await resp.json();
            
            if (tenantId === "__all__") {
                const results = data.results || [];
                const foundItems = results.filter(r => r.found === true);
                const subnetItems = results.filter(r => r.in_subnet === true && !r.found);
                
                if (foundItems.length === 0 && subnetItems.length === 0) {
                    setIpResult(`<span style="color: #27ae60;">✅ IP ${ip} ${currentLang === "ru" ? "не найден ни в одном тенанте" : "not found in any tenant"}</span>`);
                } else {
                    let html = "";
                    if (foundItems.length > 0) {
                        html += `<div style="color: #e67e22; margin-bottom: 0.5rem;">⚠️ IP ${ip} ${currentLang === "ru" ? "найден в следующих тенантах" : "found in following tenants"}:</div>`;
                        html += '<ul style="margin: 0; padding-left: 1.5rem;">';
                        for (const item of foundItems) {
                            const ttlText = item.ttl_remaining ? ` (TTL: ${item.ttl_remaining})` : "";
                            html += `<li><strong>${item.tenant_name}</strong> → ${item.list_name || "Aggregation blacklist"}${ttlText}</li>`;
                        }
                        html += '</ul>';
                    }
                    if (subnetItems.length > 0) {
                        html += `<div style="color: #3498db; margin-bottom: 0.5rem; margin-top: 0.5rem;">🔗 IP ${ip} ${currentLang === "ru" ? "является частью подсети в" : "is part of subnet in"}:</div>`;
                        html += '<ul style="margin: 0; padding-left: 1.5rem;">';
                        for (const item of subnetItems) {
                            const subnets = item.containing_subnets ? item.containing_subnets.join(", ") : "";
                            html += `<li><strong>${item.tenant_name}</strong> → ${item.list_name || "Aggregation blacklist"} (${subnets})</li>`;
                        }
                        html += '</ul>';
                    }
                    setIpResult(html);
                }
            } else {
                if (data.found) {
                    const ttlText = data.ttl_remaining ? ` (TTL: ${data.ttl_remaining})` : "";
                    setIpResult(`<span style="color: #e67e22;">⚠️ IP ${ip} ${currentLang === "ru" ? "найден в списке" : "found in list"}${ttlText}</span>`);
                } else if (data.in_subnet) {
                    const subnetsText = data.containing_subnets ? data.containing_subnets.join(", ") : "";
                    setIpResult(`<span style="color: #3498db;">🔗 IP ${ip} ${currentLang === "ru" ? "является частью подсети" : "is part of subnet"}: ${subnetsText}</span>`);
                } else {
                    setIpResult(`<span style="color: #27ae60;">✅ IP ${ip} ${currentLang === "ru" ? "не найден в списке" : "not found in list"}</span>`);
                }
            }
        } catch (err) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Ошибка проверки" : "Check error"}: ${err}</span>`, true);
            log("Check IP error: " + err);
        }
    }

    async function getPermanentIps() {
        const tenantId = document.getElementById("ip-tenant").value;
        
        if (!tenantId) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите тенант" : "Select tenant"}</span>`, true);
            return;
        }
        
        let listId = null;
        if (tenantId !== "__all__") {
            listId = document.getElementById("ip-list").value;
            if (!listId) {
                setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите глобальный список" : "Select global list"}</span>`, true);
                return;
            }
        }
        
        setIpResult(`<span>${currentLang === "ru" ? "Получение permanent IP..." : "Getting permanent IPs..."}</span>`);
        
        try {
            const resp = await fetch("/api/global_lists/get_permanent_ips", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tenant_id: tenantId, list_id: listId }),
            });
            
            const data = await resp.json();
            
            if (tenantId === "__all__") {
                const results = data.results || [];
                const totalPermanent = data.total_permanent_ips || 0;
                
                let html = `<div style="margin-bottom: 0.5rem;"><strong>${currentLang === "ru" ? "Permanent IP найдено" : "Permanent IPs found"}: ${totalPermanent}</strong></div>`;
                
                let hasPermanent = false;
                for (const r of results) {
                    const ips = r.permanent_ips || [];
                    if (ips.length > 0) {
                        hasPermanent = true;
                        html += `<div style="margin: 0.5rem 0;"><strong>${r.tenant_name}</strong> (${r.list_name || "Aggregation blacklist"}): ${ips.length} permanent IP</div>`;
                        html += '<div style="font-family: monospace; font-size: 0.85rem; padding-left: 1rem; color: #7f8c8d;">' + ips.slice(0, 20).join(", ") + (ips.length > 20 ? `... и ещё ${ips.length - 20}` : "") + '</div>';
                    }
                }
                
                if (!hasPermanent) {
                    html += `<div style="color: #27ae60;">${currentLang === "ru" ? "Permanent IP не найдено" : "No permanent IPs found"}</div>`;
                }
                
                setIpResult(html);
            } else {
                const permanentIps = data.permanent_ips || [];
                const count = data.count || 0;
                
                if (count === 0) {
                    setIpResult(`<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "Permanent IP не найдено" : "No permanent IPs found"}</span>`);
                } else {
                    let html = `<div style="margin-bottom: 0.5rem;"><strong>${currentLang === "ru" ? "Permanent IP найдено" : "Permanent IPs found"}: ${count}</strong></div>`;
                    html += '<div style="font-family: monospace; font-size: 0.85rem;">' + permanentIps.join(", ") + '</div>';
                    setIpResult(html);
                }
            }
        } catch (err) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Ошибка" : "Error"}: ${err}</span>`, true);
            log("Get permanent IPs error: " + err);
        }
    }

    async function removePermanentIps() {
        const tenantId = document.getElementById("ip-tenant").value;
        
        if (!tenantId) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите тенант" : "Select tenant"}</span>`, true);
            return;
        }
        
        let listId = null;
        if (tenantId !== "__all__") {
            listId = document.getElementById("ip-list").value;
            if (!listId) {
                setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите глобальный список" : "Select global list"}</span>`, true);
                return;
            }
        }
        
        const confirmMsg = tenantId === "__all__"
            ? (currentLang === "ru" ? "⚠️ Это удалит ВСЕ permanent IP из ВСЕХ тенантов! Продолжить?" : "⚠️ This will remove ALL permanent IPs from ALL tenants! Continue?")
            : (currentLang === "ru" ? "⚠️ Это удалит ВСЕ permanent IP из выбранного списка! Продолжить?" : "⚠️ This will remove ALL permanent IPs from the selected list! Continue?");
        
        if (!confirm(confirmMsg)) {
            return;
        }
        
        setIpResult(`<span>${currentLang === "ru" ? "Удаление permanent IP..." : "Removing permanent IPs..."}</span>`);
        
        try {
            const resp = await fetch("/api/global_lists/remove_permanent_ips", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tenant_id: tenantId, list_id: listId }),
            });
            
            const data = await resp.json();
            
            if (tenantId === "__all__") {
                const summary = data.summary || {};
                const totalRemoved = summary.total_removed || 0;
                const successCount = summary.success || 0;
                const failedCount = summary.failed || 0;
                
                if (totalRemoved === 0) {
                    setIpResult(`<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "Permanent IP не найдено для удаления" : "No permanent IPs found to remove"}</span>`);
                } else {
                    let html = `<div style="color: #27ae60; margin-bottom: 0.5rem;"><strong>✅ ${currentLang === "ru" ? "Удалено" : "Removed"} ${totalRemoved} permanent IP</strong></div>`;
                    html += `<div>${currentLang === "ru" ? "Успешно" : "Success"}: ${successCount}/${summary.total_tenants || 0} ${currentLang === "ru" ? "тенантов" : "tenants"}`;
                    if (failedCount > 0) {
                        html += ` (${failedCount} ${currentLang === "ru" ? "ошибок" : "errors"})`;
                    }
                    html += '</div>';
                    setIpResult(html);
                }
            } else {
                if (data.removed_count === 0) {
                    setIpResult(`<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "Permanent IP не найдено для удаления" : "No permanent IPs found to remove"}</span>`);
                } else {
                    const ipsList = (data.removed_ips || []).slice(0, 10).join(", ");
                    const moreText = data.removed_ips.length > 10 ? ` +${data.removed_ips.length - 10}...` : "";
                    setIpResult(`<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "Удалено" : "Removed"} ${data.removed_count} permanent IP: ${ipsList}${moreText}</span>`);
                }
            }
        } catch (err) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Ошибка" : "Error"}: ${err}</span>`, true);
            log("Remove permanent IPs error: " + err);
        }
    }

    async function setPermanentIps7Days() {
        const tenantId = document.getElementById("ip-tenant").value;
        
        if (!tenantId) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите тенант" : "Select tenant"}</span>`, true);
            return;
        }
        
        let listId = null;
        if (tenantId !== "__all__") {
            listId = document.getElementById("ip-list").value;
            if (!listId) {
                setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Выберите глобальный список" : "Select global list"}</span>`, true);
                return;
            }
        }
        
        const confirmMsg = tenantId === "__all__"
            ? (currentLang === "ru" ? "⚠️ Это установит TTL 7 дней для ВСЕХ permanent IP во ВСЕХ тенантах! Продолжить?" : "⚠️ This will set 7 days TTL for ALL permanent IPs in ALL tenants! Continue?")
            : (currentLang === "ru" ? "⚠️ Это установит TTL 7 дней для ВСЕХ permanent IP в выбранном списке! Продолжить?" : "⚠️ This will set 7 days TTL for ALL permanent IPs in the selected list! Continue?");
        
        if (!confirm(confirmMsg)) {
            return;
        }
        
        setIpResult(`<span>${currentLang === "ru" ? "Установка TTL 7 дней для permanent IP..." : "Setting 7 days TTL for permanent IPs..."}</span>`);
        
        try {
            const resp = await fetch("/api/global_lists/set_permanent_ips_7_days", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tenant_id: tenantId, list_id: listId }),
            });
            
            const data = await resp.json();
            
            if (tenantId === "__all__") {
                const summary = data.summary || {};
                const totalProcessed = summary.total_processed || 0;
                const successCount = summary.success || 0;
                const failedCount = summary.failed || 0;
                
                if (totalProcessed === 0) {
                    setIpResult(`<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "Permanent IP не найдено" : "No permanent IPs found"}</span>`);
                } else {
                    let html = `<div style="color: #27ae60; margin-bottom: 0.5rem;"><strong>✅ ${currentLang === "ru" ? "Установлено TTL 7 дней для" : "Set 7 days TTL for"} ${totalProcessed} permanent IP</strong></div>`;
                    html += `<div>${currentLang === "ru" ? "Успешно" : "Success"}: ${successCount}/${summary.total_tenants || 0} ${currentLang === "ru" ? "тенантов" : "tenants"}`;
                    if (failedCount > 0) {
                        html += ` (${failedCount} ${currentLang === "ru" ? "ошибок" : "errors"})`;
                    }
                    html += '</div>';
                    setIpResult(html);
                }
            } else {
                if (data.processed_count === 0) {
                    setIpResult(`<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "Permanent IP не найдено" : "No permanent IPs found"}</span>`);
                } else {
                    const ipsList = (data.processed_ips || []).slice(0, 10).join(", ");
                    const moreText = data.processed_ips.length > 10 ? ` +${data.processed_ips.length - 10}...` : "";
                    setIpResult(`<span style="color: #27ae60;">✅ ${currentLang === "ru" ? "Установлено TTL 7 дней для" : "Set 7 days TTL for"} ${data.processed_count} permanent IP: ${ipsList}${moreText}</span>`);
                }
            }
        } catch (err) {
            setIpResult(`<span style="color: #e74c3c;">❌ ${currentLang === "ru" ? "Ошибка" : "Error"}: ${err}</span>`, true);
            log("Set 7 days TTL error: " + err);
        }
    }

    function showLoading() {
      const overlay = document.getElementById('loading-overlay');
      overlay.classList.remove('hidden-overlay');
    }
    function hideLoading() {
      const overlay = document.getElementById('loading-overlay');
      overlay.classList.add('hidden-overlay');
    }

    function showConnectionError(message) {
      const logEl = document.getElementById("log");
      const errorDiv = document.createElement("div");
      errorDiv.style.color = "#e74c3c";
      errorDiv.style.fontWeight = "bold";
      errorDiv.style.marginBottom = "0.5rem";
      errorDiv.textContent = "❌ " + message;
      logEl.prepend(errorDiv);
    }

    function showNotification(message, type = "info") {
      const existing = document.getElementById("notification-container");
      if (existing) existing.remove();

      const container = document.createElement("div");
      container.id = "notification-container";
      container.style.cssText = `
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 10000;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      `;

      const notification = document.createElement("div");
      const bgColor = type === "error" ? "#e74c3c" : type === "success" ? "#27ae60" : "#3498db";
      notification.style.cssText = `
        background: ${bgColor};
        color: white;
        padding: 0.75rem 1.25rem;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        font-weight: 500;
        max-width: 400px;
        animation: slideIn 0.3s ease-out;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
      `;

      const messageSpan = document.createElement("span");
      messageSpan.textContent = message;
      messageSpan.style.flex = "1";

      const closeBtn = document.createElement("button");
      closeBtn.innerHTML = "&times;";
      closeBtn.style.cssText = `
        background: transparent;
        border: none;
        color: white;
        font-size: 1.25rem;
        cursor: pointer;
        padding: 0;
        line-height: 1;
        opacity: 0.8;
      `;
      closeBtn.onmouseover = () => closeBtn.style.opacity = "1";
      closeBtn.onmouseout = () => closeBtn.style.opacity = "0.8";
      closeBtn.onclick = () => {
        notification.style.opacity = "0";
        notification.style.transition = "opacity 0.3s";
        setTimeout(() => container.remove(), 300);
      };

      notification.appendChild(messageSpan);
      notification.appendChild(closeBtn);

      container.appendChild(notification);
      document.body.appendChild(container);

      setTimeout(() => {
        notification.style.opacity = "0";
        notification.style.transition = "opacity 0.3s";
        setTimeout(() => container.remove(), 300);
      }, 10000);
    }

    // Policy Manager functions
    async function onPolicyTenantChange() {
      // Placeholder for future tenant-specific logic
      console.log("Policy tenant changed to: " + document.getElementById("policy-tenant").value);
    }

    async function downloadPolicyJson() {
      const tenantId = document.getElementById("policy-tenant").value;
      const addWhitelist = document.getElementById("add-whitelist-to-aggregation-rule").checked;
      const whitelistName = document.getElementById("whitelist-name").value.trim() || "white_list";

      if (!addWhitelist) {
        setPolicyResult("⚠️ " + (currentLang === "ru" ? "Выберите опцию для изменения" : "Select a modification option"), "error");
        return;
      }

      setPolicyResult("⏳ " + (currentLang === "ru" ? "Генерация JSON..." : "Generating JSON..."), "info");
      console.log("Generating policy JSON for tenant " + tenantId + " with whitelist " + whitelistName);

      try {
        const resp = await fetch("/api/policy/download", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tenant_id: tenantId,
            add_whitelist: addWhitelist,
            whitelist_name: whitelistName,
          })
        });

        if (!resp.ok) {
          const data = await resp.json();
          setPolicyResult("❌ " + (currentLang === "ru" ? "Ошибка генерации" : "Generation failed") + ": " + (data.error || resp.statusText), "error");
          console.error("Download JSON failed: " + JSON.stringify(data));
          return;
        }

        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, -5);
        a.download = "policy_" + tenantId + "_" + timestamp + ".json";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        setPolicyResult("✅ " + (currentLang === "ru" ? "JSON скачан" : "JSON downloaded"), "success");
        console.log("Policy JSON downloaded successfully for tenant " + tenantId);
      } catch (err) {
        setPolicyResult("❌ " + (currentLang === "ru" ? "Ошибка" : "Error") + ": " + err, "error");
        console.error("Download error: " + err);
      }
    }

    async function applyPolicyChanges() {
      const tenantId = document.getElementById("policy-tenant").value;
      const addWhitelist = document.getElementById("add-whitelist-to-aggregation-rule").checked;
      const whitelistName = document.getElementById("whitelist-name").value.trim() || "white_list";

      if (!addWhitelist) {
        setPolicyResult("⚠️ " + (currentLang === "ru" ? "Выберите опцию для изменения" : "Select a modification option"), "error");
        return;
      }

      const confirmMsg = currentLang === "ru"
        ? "Вы уверены, что хотите применить изменения к " + (tenantId === "__all__" ? "всем тенантам" : "тенанту") + "?"
        : "Are you sure you want to apply changes to " + (tenantId === "__all__" ? "all tenants" : "tenant") + "?";

      if (!confirm(confirmMsg)) return;

      setPolicyResult("⏳ " + (currentLang === "ru" ? "Применение изменений..." : "Applying changes..."), "info");
      console.log("Applying policy changes for tenant " + tenantId + " with whitelist " + whitelistName);

      try {
        const resp = await fetch("/api/policy/apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tenant_id: tenantId,
            add_whitelist: addWhitelist,
            whitelist_name: whitelistName,
          })
        });

        const data = await resp.json();
        if (!resp.ok) {
          setPolicyResult("❌ " + (currentLang === "ru" ? "Ошибка применения" : "Apply failed") + ": " + (data.error || resp.statusText), "error");
          console.error("Apply failed: " + JSON.stringify(data));
          return;
        }

        if (tenantId === "__all__" && data.results) {
          const successCount = data.results.filter(r => !r.error && !r.skipped).length;
          const skippedCount = data.results.filter(r => r.skipped).length;
          const failCount = data.results.filter(r => r.error).length;
          setPolicyResult(
            "✅ " + (currentLang === "ru"
              ? "Применено: " + successCount + ", Пропущено: " + skippedCount + ", Ошибок: " + failCount
              : "Applied: " + successCount + ", Skipped: " + skippedCount + ", Failed: " + failCount),
            successCount > 0 ? "success" : (skippedCount > 0 ? "info" : "error")
          );
          console.log("Batch apply completed: " + successCount + " success, " + skippedCount + " skipped, " + failCount + " failed");
        } else {
          if (data.skipped) {
            setPolicyResult("ⓘ " + (currentLang === "ru" ? "Изменений не требуется (всё уже применено)" : "No changes needed (already applied)"), "info");
            console.log("Policy changes skipped: already applied for tenant " + tenantId);
          } else {
            setPolicyResult("✅ " + (currentLang === "ru" ? "Изменения применены" : "Changes applied"), "success");
            console.log("Policy changes applied successfully for tenant " + tenantId);
          }
        }
      } catch (err) {
        setPolicyResult("❌ " + (currentLang === "ru" ? "Ошибка" : "Error") + ": " + err, "error");
        console.error("Apply error: " + err);
      }
    }

    function setPolicyResult(msg, type) {
      const el = document.getElementById("policy-result");
      if (!el) return;
      el.className = "result-box " + (type || "info");
      el.innerHTML = msg;
    }

    function switchTab(tabId) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.getElementById(`tab-${tabId}`).classList.add('active');
      document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
      document.querySelector(`.tab-button[data-tab="${tabId}"]`).classList.add('active');
      if (tabId === 'log') adjustLogSize();
    }

    async function initUi() {
      showLoading();
      adjustLogSize();
      try {
        await loadSettings();
        await loadTenants();
        await loadLocalExports();
        setTheme(currentTheme);
        adjustLogSize();
        document.getElementById("tenant-select").addEventListener("change", () => {
          loadApplicationsForSourceTenant();
          updateLocalFiles("rule");
          updateLocalFiles("action");
        });
        document.getElementById("ip-tenant").addEventListener("change", onIpTenantChange);
        document.getElementById("policy-tenant").addEventListener("change", onPolicyTenantChange);
      } catch (err) {
        let errorMsg = err.message || String(err);
        if (errorMsg === "authentication_failed") {
          // Notification already shown in loadTenants
          log("Initialization failed: authentication error");
        } else if (errorMsg.includes("HTTP 401") || errorMsg.includes("403")) {
          errorMsg = "Authentication failed. Please check login/password or API token.";
          showNotification(errorMsg, "error");
          log("Initialization error: " + errorMsg);
          showConnectionError(errorMsg + " – please go to Settings, correct the data and reload the page.");
        } else if (errorMsg.includes("Failed to fetch") || errorMsg.includes("NetworkError")) {
          errorMsg = "Cannot connect to the backend API. Check AF server URL and network.";
          showNotification(errorMsg, "error");
          log("Initialization error: " + errorMsg);
          showConnectionError(errorMsg + " – please go to Settings, correct the data and reload the page.");
        } else {
          log("Initialization error: " + errorMsg);
          showConnectionError(errorMsg + " – please go to Settings, correct the data and reload the page.");
        }
      } finally {
        hideLoading();
      }
    }

    window.addEventListener("load", adjustLogSize);
    initUi().catch(e => log("Error: " + e));
  </script>
</body>
</html>
"""