# Trading Bot Experimental (Solo Asistente)

**IMPORTANTE:** Este bot NO opera ni toma decisiones finales. Solo analiza y sugiere señales de trading en tiempo real para acciones, usando indicadores técnicos y datos reales. El usuario debe decidir y asumir el riesgo final.

## ¿Qué hace este bot?
- Analiza velas de 1 hora de acciones (tickers provistos por el usuario).
- Calcula indicadores técnicos avanzados (RSI, ATR, ADX, Supertrend, EMAs, MACD, Bollinger Bands, Stochastic, volumen, etc.).
- Detecta señales de COMPRA, VENTA o NEUTRA por vela, justificando cada señal con los indicadores que la activan.
- Guarda resultados en la subcarpeta `results/` en formato CSV y JSON.
- NO usa datos de ejemplo ni valores hardcodeados. Todo es real y en tiempo real.
- Usa logging para trazabilidad.

## ¿Qué NO hace?
- No opera ni ejecuta órdenes.
- No usa datos de prueba ni valores por defecto.
- No toma decisiones finales: solo sugiere.

## ¿Cómo se usa?
1. Instala dependencias: `pip install yfinance pandas numpy ta-lib`
2. Edita el archivo `trading_bot.py` y coloca tus tickers reales en el diccionario `tickers` (ejemplo: `{'AAPL': 'AAPL', 'MSFT': 'MSFT'}`).
3. Ejecuta el script:
   ```
   python trading_bot.py
   ```
4. Los resultados aparecerán en la carpeta `results/` como CSV y JSON.

## ¿Cómo interpretar los resultados?
- Cada fila es una vela (1h) con:
  - `datetime`: Fecha/hora de la vela.
  - `signal`: COMPRA, VENTA o NEUTRA.
  - `indicadores`: Lista de indicadores que justifican la señal.
  - `take_profit` y `stop_loss`: Niveles sugeridos (solo referencia, no ejecución).

## Disclaimers
- **Este bot es experimental y no garantiza resultados.**
- El análisis es solo informativo y no constituye asesoramiento financiero.
- El usuario es responsable de cualquier decisión de inversión.
- No uses este bot para operar automáticamente.

## Formato y calidad
- Código modular, con manejo robusto de errores.
- Compatible con Ruff y Black (ver pyproject.toml).
- Logging en vez de print. 