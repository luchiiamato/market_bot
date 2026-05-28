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
python3 -m uvicorn services.api.app:app --host 0.0.0.0 --reload
```

- app local: `http://127.0.0.1:8000/app/`
- docs API: `http://127.0.0.1:8000/docs`

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
