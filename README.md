# Market Bot

Workspace de analisis para inversores ARG con:

- analisis tecnico deterministico y probabilistico
- perfil inversor y portfolio manual
- importador Balanz `.xlsx`
- valuacion CEDEAR/stock y comparacion contra benchmarks ARG
- news, earnings y market overview
- UI web responsive en `apps/web/prototype`

## Estructura

- `services/api` — FastAPI
- `packages/engine` — analisis, ranking, validacion
- `packages/identity` — auth local, sesiones, audit log
- `packages/portfolio` — posiciones, import Balanz, P&L
- `packages/reference_data` — benchmarks ARG, news, earnings
- `apps/web/prototype` — frontend estatico para Vercel o servido localmente por FastAPI

## Desarrollo local

```bash
./scripts/run_workspace.sh
```

Con el `.env` default:

- modo: `local`
- app local: `http://127.0.0.1:8000/app/`
- docs API: `http://127.0.0.1:8000/docs`

Variables clave en `.env`:

- `MARKET_BOT_RUNTIME_MODE=local|host`
- `MARKET_BOT_LOCAL_BACKEND_HOST`
- `MARKET_BOT_LOCAL_BACKEND_PORT`
- `MARKET_BOT_HOSTED_API_BASE`

Comportamiento:

- `local`: levanta FastAPI local y sirve frontend + backend desde el mismo origen.
- `host`: sirve el frontend local por `http.server` pero apuntando al backend remoto configurado en `MARKET_BOT_HOSTED_API_BASE`.

## Tests

```bash
python3 -m pytest -q
```

## Deploy recomendado

- frontend: Vercel
- backend: Fly.io
- DB: SQLite persistida en Fly volume

Guia:

- [Deploy Vercel + Fly](/Users/lucianoamato/Desktop/Proyectos/market_bot/market_bot/docs/deploy-vercel-fly.md)
- [Guia Beta Tester](/Users/lucianoamato/Desktop/Proyectos/market_bot/market_bot/docs/beta-tester-guide.md)

## Variables utiles

- `MARKET_BOT_DB_PATH`
- `CORS_ALLOW_ORIGINS`
- `CORS_ALLOW_ORIGIN_REGEX`
- `MARKET_BOT_API_BASE`
- `MARKETAUX_API_KEY`

Ejemplos:

- [.env.example](/Users/lucianoamato/Desktop/Proyectos/market_bot/market_bot/.env.example)
- [apps/web/prototype/.env.production.example](/Users/lucianoamato/Desktop/Proyectos/market_bot/market_bot/apps/web/prototype/.env.production.example)
