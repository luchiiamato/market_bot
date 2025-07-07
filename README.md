# Bot de Señales de Mercado 📈

Este bot analiza acciones y ETFs para generar señales de trading basadas en análisis técnico, predicción de precios y sentimiento del mercado.

## 📊 Indicadores Técnicos

### Medias Móviles (SMA)
- **SMA-20**: Media móvil de 20 días. Muestra la tendencia a corto plazo.
  - Cuando el precio está por encima: Señal alcista
  - Cuando el precio está por debajo: Señal bajista
- **SMA-50**: Media móvil de 50 días. Muestra la tendencia a medio plazo.
  - Cruce de SMA-20 por encima de SMA-50: Confirmación de tendencia alcista
  - Cruce de SMA-20 por debajo de SMA-50: Confirmación de tendencia bajista
- **SMA-200**: Media móvil de 200 días. Muestra la tendencia a largo plazo.
  - Precio por encima: Mercado en tendencia alcista de largo plazo
  - Precio por debajo: Mercado en tendencia bajista de largo plazo

### Medias Móviles Exponenciales (EMA)
- **EMA**: Similar a SMA pero da más peso a los precios recientes
  - Reacciona más rápido a cambios de precio que la SMA
  - Reduce el "retraso" (lag) en las señales
  - Fórmula: EMA = (Precio actual × k) + (EMA anterior × (1 - k))
    donde k = 2/(n+1) y n es el número de períodos
- **EMA-12 y EMA-26**: Usadas para calcular el MACD
  - Diferencia entre estas líneas forma la línea MACD
- **EMA-20**: Similar a SMA-20 pero más reactiva
- **EMA-50 y EMA-200**: Para tendencias de medio y largo plazo
  - Más sensibles a cambios recientes que sus equivalentes SMA

### RSI (Índice de Fuerza Relativa)
- **Rango**: 0-100
- **Sobrecompra**: > 70
  - El activo está potencialmente sobrevalorado
  - Posible corrección a la baja
- **Sobreventa**: < 30
  - El activo está potencialmente infravalorado
  - Posible rebote al alza
- **Neutral**: 30-70
  - Mercado en equilibrio
  - Sin señales claras

  
### MACD (Convergencia/Divergencia de Medias Móviles)
- **Línea MACD**: Diferencia entre EMA-12 y EMA-26
- **Línea de Señal**: Media móvil de 9 días del MACD
- **Interpretación**:
  - MACD cruza por encima de la señal: Momentum alcista
  - MACD cruza por debajo de la señal: Momentum bajista

### Bandas de Bollinger
- **Banda Superior**: SMA-20 + (2 × Desviación Estándar)
- **Banda Media**: SMA-20
- **Banda Inferior**: SMA-20 - (2 × Desviación Estándar)
- **Interpretación**:
  - Precio cerca de banda superior: Posible sobrecompra
  - Precio cerca de banda inferior: Posible sobreventa
  - Bandas estrechas: Baja volatilidad
  - Bandas anchas: Alta volatilidad

## 🎯 Señales de Trading

### Tipos de Señales
1. **Comprar**
   - Tendencia alcista confirmada
   - RSI en sobreventa
   - Volumen confirmando movimiento
   - Múltiples indicadores alineados

2. **Vender**
   - Tendencia bajista confirmada
   - RSI en sobrecompra
   - Volumen confirmando movimiento
   - Múltiples indicadores alineados

3. **Mantener**
   - Mercado lateral
   - Señales contradictorias
   - Alta volatilidad
   - Falta de confirmación

### Predicciones de Precio
- **"sube (tendencia alcista X/3)"**
  - X = 3: Tendencia alcista fuerte (máxima confianza)
  - X = 2: Tendencia alcista moderada
  - X = 1: Tendencia alcista débil

- **"baja (tendencia bajista X/3)"**
  - X = 3: Tendencia bajista fuerte (máxima confianza)
  - X = 2: Tendencia bajista moderada
  - X = 1: Tendencia bajista débil

- **"mantener (tendencia lateral)"**
  - Mercado sin dirección clara
  - Señales mixtas
  - Baja confianza en predicción

## 📈 Factores de Confianza

### Cálculo de Confianza (0.5 - 0.95)
1. **Fuerza del Precio (30%)**
   - Magnitud del movimiento
   - Consistencia de la tendencia

2. **Volumen (20%)**
   - Volumen vs promedio
   - Confirmación de movimiento

3. **Volatilidad (30%)**
   - ATR (Average True Range)
   - Estabilidad del mercado

4. **Tendencia (20%)**
   - Alineación de timeframes
   - Fuerza de la tendencia

### Ajustes de Confianza
- **Aumenta 20%** con tendencias fuertes (score ≥ 2)
- **Disminuye 20%** con tendencias débiles (score = 0)
- **Disminuye 20%** en alta volatilidad

## ⚠️ Alertas de Riesgo

1. **Divergencia de Tendencias**
   - Tendencia corto plazo vs largo plazo
   - Posible cambio de dirección

2. **Condiciones Extremas RSI**
   - RSI > 80: Sobrecompra extrema
   - RSI < 20: Sobreventa extrema

3. **Volumen Inusual**
   - > 3x promedio: Posible movimiento significativo
   - < 0.5x promedio: Movimiento débil

## 📊 Interpretación del Reporte

El archivo `reporte_final.csv` contiene:
- Ticker
- Precio Actual
- Señal (Comprar/Vender/Mantener)
- Razones detalladas
- Predicción de dirección
- Nivel de confianza
- Stop Loss
- Take Profit
- Sentimiento neto

## 🛠️ Requisitos Técnicos

- Python 3.8+
- pandas
- numpy
- yfinance
- transformers (para análisis de sentimiento)

## ⚠️ Advertencia

Este bot es una herramienta de análisis y no constituye asesoramiento financiero. Siempre realice su propio análisis y considere su tolerancia al riesgo antes de operar.