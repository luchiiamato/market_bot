# Deploy: Vercel (frontend) + Fly.io (backend)

Guía paso a paso para deployar Market Bot. Backend FastAPI en Fly.io (region GRU, São Paulo, cerca de AR) y frontend estático en Vercel.

Importante: no asumas que Fly o Vercel siguen siendo `$0` para cuentas nuevas. El path técnico sigue siendo válido, pero el costo real depende de tu plan actual, créditos y pricing vigente al momento del deploy.

## 1. Prerequisitos

- Cuenta en [Vercel](https://vercel.com) y [Fly.io](https://fly.io).
- Vercel CLI: `npm i -g vercel`.
- Fly CLI: `curl -L https://fly.io/install.sh | sh`.
- Repo clonado localmente, en la raíz `market_bot/`.
- Opcional pero recomendado: correr `./scripts/deploy_preflight.sh` antes del primer deploy.

## 2. Backend deploy (Fly.io)

```bash
fly auth login
cd market_bot/
fly launch --no-deploy
```

`fly launch` te va a preguntar nombre de app (sugerido: `market-bot-api`), region (elegí `gru`), y si querés Postgres/Redis (decí que no, usamos SQLite).

Creá el volume para que la DB persista entre deploys:

```bash
fly volumes create market_bot_data --region gru --size 1
```

En `fly.toml` asegurate de tener el mount:

```toml
[[mounts]]
  source = "market_bot_data"
  destination = "/data"
```

Y la env var apuntando ahí: `MARKET_BOT_DB_PATH=/data/market_bot.db`.

Seteá secrets:

```bash
fly secrets set CORS_ALLOW_ORIGINS=https://market-bot.vercel.app
fly secrets set CORS_ALLOW_ORIGIN_REGEX='^https://market-bot(?:-[a-z0-9-]+)?\.vercel\.app$'
fly secrets set MARKET_BOT_DB_PATH=/data/market_bot.db
fly deploy
```

`CORS_ALLOW_ORIGIN_REGEX` existe porque los previews de Vercel no usan un solo host fijo y `CORSMiddleware` no interpreta `https://*.vercel.app` dentro de `allow_origins`.

Verificá:

```bash
curl https://market-bot-api.fly.dev/health
# → {"status":"ok"}
```

Nota: en el backend desplegado por Fly, `/` redirige a `/docs` si el frontend no está incluido en la imagen. El frontend público vive en Vercel.

## 3. Frontend deploy (Vercel)

```bash
cd apps/web/prototype/
vercel link
```

En el dashboard de Vercel (Project → Settings → Environment Variables), seteá para **Production** y **Preview**:

```
MARKET_BOT_API_BASE=https://market-bot-api.fly.dev
```

Después:

```bash
vercel --prod
```

Abrí `https://market-bot.vercel.app`, registrá un usuario y confirmá que el login funciona.

## 4. Troubleshooting común

- **CORS errors en consola** → el valor de `CORS_ALLOW_ORIGINS` en Fly tiene que coincidir exactamente con la URL de Vercel (sin trailing slash, con https).
- **401 después del login** → el frontend tiene que enviar `Authorization: Bearer <token>` en cada request. Revisá DevTools → Network.
- **Fly app duerme y tarda varios segundos en responder** → con `auto_stop_machines = "stop"` y `min_machines_running = 0` esto es esperado. Si te molesta, subí `min_machines_running = 1` o desactivá el auto-stop; eso puede aumentar el costo.
- **La DB se borró tras deploy** → el volume no está montado. Corré `fly volumes list` para confirmar que existe y revisá la sección `[mounts]` en `fly.toml`. La env `MARKET_BOT_DB_PATH` tiene que apuntar a `/data/market_bot.db`, no a `./market_bot.db`.
- **Cold start lento la primera request del día** → normal si la máquina estaba detenida. Trade-off conocido del config actual.
- **Deploy de Fly falla con "out of memory"** → la imagen Docker pesa mucho. Subí la VM: `fly scale memory 512` y redeployá.

## 5. Rollback

**Fly.io:**

```bash
fly releases
fly releases rollback <version>
```

**Vercel:** dashboard → Deployments → buscá un deploy verde anterior → menú de tres puntos → "Promote to Production".

Si rolleaste el backend y el frontend quedó desincronizado, hacé rollback de ambos en el mismo orden inverso al deploy (frontend primero, backend después).
