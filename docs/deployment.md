# Развёртывание

## Быстрый старт
1. Скопировать `.env.example` в `.env`.
2. При необходимости скорректировать `DATABASE_URL`, `REDIS_URL`, `STORAGE_ROOT`.
3. Запустить `docker compose up --build`.
4. Открыть `http://localhost:8080`.

## Dev-режим
- `docker compose -f docker-compose.dev.yml up --build`
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

## Demo mode
- По умолчанию включён `APP_DEMO_MODE=true`.
- Используется `FakeLLMAdapter`.
- Dry-run deploy включён по умолчанию.

## Реальный deploy
- Выключить `DEPLOYMENT_DRY_RUN_DEFAULT`, либо выбрать `dry_run=false` в UI.
- Убедиться, что локально доступен Docker.
- Для MVP выполняется безопасная проверка deployment manifest через `docker compose config`.

