# Dar acceso a un tester externo — opciones

> Estado: la app corre local en `http://127.0.0.1:8000` (frontend + API en el
> mismo origen, servido por FastAPI en `/app/`). El frontend es same-origin-aware,
> así que cualquier dominio público que apunte al server funciona sin tocar config.

## ⭐ Recomendado: Opción A (túnel). Fly NO es gratis; Heroku borra el SQLite al reiniciar.

## Opción A — Túnel cloudflared (más rápido, hoy, $0) ⭐ RECOMENDADO

**Cuándo:** querés que un tester entre AHORA, tu Mac queda prendida.
**Tradeoff:** expone tu máquina local (con la DB SQLite y las keys del `.env`) a
internet mientras el túnel está activo. Para una DB de prueba está OK. Cerralo
cuando termines (Ctrl+C).

```bash
# 1. Instalar cloudflared (una vez)
brew install cloudflared

# 2. Asegurarte que el server está corriendo (con la Gemini key cargada)
cd /Users/lucianoamato/Desktop/Proyectos/market_bot/market_bot
set -a; source .env; set +a
python3 -m uvicorn services.api.app:app --host 127.0.0.1 --port 8000 --loop asyncio --http h11

# 3. En OTRA terminal, levantar el túnel
cloudflared tunnel --url http://localhost:8000
```

Cloudflared imprime una URL tipo `https://xxxx-yyyy.trycloudflare.com`.
**Pasale al tester:** `https://xxxx-yyyy.trycloudflare.com/app/`

El tester se registra con usuario/clave, carga su perfil, importa su Balanz o
suma posiciones, y prueba el chat (Gemini ya configurado).

> Nota: el warmup del ranking tarda ~65s la primera vez tras arrancar el server.
> Esperá a ver `rankings warmup done` en el log antes de pasar el link, así el
> tester no espera.

## Opción C — Heroku (tenés créditos) — solo si querés permanente

Heroku sirve si querés algo que no dependa de tu Mac y tenés créditos. **Caveat
importante**: el filesystem de los dynos es efímero — la DB SQLite se borra en cada
reinicio/deploy. Para Heroku habría que migrar a **Heroku Postgres** (add-on) o
aceptar que los datos del tester se pierden seguido. Es trabajo extra (Sprint 4-Heroku).
Para un tester rápido, el túnel (Opción A) lo evita. Si querés ir por Heroku, decime
y armo el `Procfile` + la migración a Postgres.

## Opción B — Deploy real a Fly.io (permanente) — descartado: NO es gratis

**Cuándo:** querés algo estable que siga vivo sin tu máquina.
**Tradeoff:** necesita cuenta Fly + login + ~10 min. Scaffolding ya está listo
(`Dockerfile`, `fly.toml`).

```bash
# 1. Instalar flyctl + login (una vez)
brew install flyctl
fly auth login

# 2. Crear la app + volumen (una vez). El nombre debe ser único global.
cd /Users/lucianoamato/Desktop/Proyectos/market_bot/market_bot
fly launch --no-deploy            # confirmá el nombre del fly.toml o cambialo
fly volumes create market_bot_data --region gru --size 1

# 3. Cargar la Gemini key como SECRET (NO va en fly.toml, que es público)
fly secrets set CHAT_GEMINI_API_KEY="<tu-key>" CHAT_GEMINI_MODEL="gemini-2.5-flash"

# 4. Deploy
fly deploy
```

La app queda en `https://<tu-app>.fly.dev/app/`. Pasale eso al tester.

**Ajustes recomendados en `fly.toml` para un demo de tester:**
- `min_machines_running = 1` (en vez de 0) → evita cold starts de varios segundos.
  El warmup del ranking corre al boot, así que mantener la máquina viva evita que
  cada tester dispare un cold start + 65s de warmup.
- `memory = "1gb"` (en vez de 512mb) → el ranking analiza 57 tickers de data 1h;
  512mb puede quedar justo y OOMear durante el warmup.

## Checklist antes de pasar el link (cualquier opción)

- [ ] Server levantado y `rankings warmup done` en el log (ranking instantáneo).
- [ ] `GET /chat/providers` muestra `gemini` con `configured: true`.
- [ ] Probaste registro → login → cargar 1 posición → analizar 1 ticker → 1 mensaje al chat.
- [ ] La DB que ve el tester es de prueba (no tu data personal si no querés compartirla).
- [ ] (Opción A) Cerrás el túnel cuando termina la sesión de testing.

## Qué reportar el tester
- ¿Pudo registrarse y entrar sin ayuda?
- ¿Los números del portfolio le cierran?
- ¿El chat respondió útil y completo (no cortado)?
- ¿Algo se vio raro / lento / confuso?
