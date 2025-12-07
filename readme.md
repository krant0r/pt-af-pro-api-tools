# pt-af-pro-api-tools (web)

Experimental web-based tools for working with PTAF PRO API.

> **Stage 1**: initialization – authenticate in PTAF, iterate over all tenants,
> export full configuration snapshots for each tenant and store them as JSON files.

Later stages will add a browser UI (FastAPI + frontend) for interactive work with
rules / actions / snapshots.

## Основные функции

1. Параметр окружения `.env` задаёт срок хранения снапшотов (количество дней),
   старше которого файлы автоматически удаляются перед новым экспортом.
2. Управление действиями в правилах через меню, аналогичное меню правил:
   1. Замена или добавление действий из других тенантов через выпадающий список
      (по совпадению имени действия, а не ID, которые отличаются в тенантах).
   2. Тиражирование выбранного действия с заменой на все остальные тенанты.
3. Восстановление конфигураций тенантов:
   1. Восстановление «защищаемых серверов» (бекендов) в текущий тенант.
   2. Восстановление «Конфигурации безопасности» с выбором версии снапшота.
4. Перенос объектов между тенантами:
   1. Перенос защищаемых веб-приложений (web applications) в другой тенант.

## Project structure

- `modules/config.py` – configuration loader (env variables, Docker secrets).
- `modules/auth.py` – token management for PTAF PRO (`/auth/refresh_tokens`, `/auth/access_tokens`).
- `modules/tenants.py` – helper for fetching list of tenants.
- `modules/snapshots.py` – stage 1 logic: export snapshots for all tenants.
- `modules/web_main.py` – FastAPI application (healthcheck and HTTP trigger for snapshots).
- `init_snapshots.py` – CLI entrypoint to run stage 1 from command line / Docker.

## Configuration

The app is configured only through environment variables and Docker secrets.
Typical variables:

- `AF_URL` – base URL of PTAF PRO, e.g. `https://ptaf.example.com`
- `API_PATH` – API prefix, usually `/api/ptaf/v4`
- `VERIFY_SSL` – `true` / `false` or path to CA bundle
- `SNAPSHOT_RETENTION_DAYS` – delete snapshot files older than the specified
  number of days before exporting new ones (empty to disable)
- `LOG_LEVEL` – `INFO`, `DEBUG`, etc.

Authentication (choose **one** approach):

1. **Static API token**

   - pass token via Docker secret, mounted as file:
     - `API_TOKEN_FILE=/run/secrets/ptaf_api_token`

2. **Username / password (JWT)**

   - Use PTAF endpoints `/auth/refresh_tokens` and `/auth/access_tokens`.
   - Pass credentials via secrets:
     - `API_LOGIN_FILE=/run/secrets/ptaf_api_login`
     - `API_PASSWORD_FILE=/run/secrets/ptaf_api_password`

Secrets themselves (files under `./secrets/*.txt`) are ignored by git via `.gitignore`.

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Export env vars for dev (example)
export AF_URL="https://ptaf.example.com"
export API_PATH="/api/ptaf/v4"
export VERIFY_SSL="false"
export API_LOGIN="your-login"
export API_PASSWORD="your-password"

# Run one-shot snapshot export
python init_snapshots.py


# через env
PTAF_ACTION_SEQUENCE=1,2 python run_sequence.py

# через параметр
python run_sequence.py --actions 1,2,3

```