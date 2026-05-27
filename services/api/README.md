# API Surface Draft

Planned service boundary:

- `GET /health`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /profile`
- `PUT /profile`
- `POST /portfolio/positions`
- `GET /portfolio/positions`
- `DELETE /portfolio/positions/{id}`
- `GET /portfolio/summary`
- `GET /benchmarks/current`
- `POST /analyze`
- `GET /rankings`
- `GET /universe`

`/analyze` returns the analysis contract from `packages/engine`.

## Current runtime notes

- `GET /rankings` defaults to `cedear_only=true`
- `GET /universe` returns the suggested CEDEAR universe for the landing page
- auth is local `username + password` backed by SQLite
- the default database path is `data/app/market_bot.db`
- portfolio loading is manual in v1
- CEDEAR valuation uses BYMA price plus underlying-ticker linkage
- benchmark comparisons use Argentina series for inflation, official USD, MEP, CCL and 30-day deposits
- Recommended local run:

```bash
python3 -m uvicorn services.api.app:app --host 0.0.0.0 --reload
```

The frontend is served by the same FastAPI app at `/app/`, so the simplest flow is:

1. Start the API with the command above.
2. Open `http://127.0.0.1:8000/app/` on the same machine.
3. From the phone, open `http://<tu-ip-local>:8000/app/` on the same Wi-Fi network.

On macOS you can inspect the local IP with:

```bash
ipconfig getifaddr en0
```

## Quick flow

1. `POST /auth/register`
2. Save the returned bearer token
3. `POST /portfolio/positions` with the token
4. `GET /portfolio/summary` to see ARS/USD P&L and benchmark comparisons
5. Open `/app/` to use the same flow from the web UI

This folder now exposes the first usable personalized workspace boundary, not just the analyzer endpoints.
