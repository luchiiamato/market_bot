# Guía de Indicadores Técnicos 📊

Esta guía explica los indicadores técnicos utilizados en el sistema de análisis y cómo interpretarlos.

## Índice de Fuerza Relativa (RSI) 

### ¿Qué es?
El RSI es un oscilador que mide la velocidad y el cambio de los movimientos de precios, oscilando entre 0 y 100.

### Cálculo
- Se calcula usando la media de las ganancias y pérdidas de los últimos 14 períodos
- Fórmula: RSI = 100 - (100 / (1 + RS))
  donde RS = Promedio de ganancias / Promedio de pérdidas

### Interpretación
- **Sobrecompra (>70)**: 
  - El activo está potencialmente sobrevalorado
  - Señal de posible corrección a la baja
  - Considerar tomar ganancias o no entrar en nuevas posiciones
- **Sobreventa (<30)**:
  - El activo está potencialmente infravalorado
  - Señal de posible rebote al alza
  - Considerar oportunidades de compra
- **Zona Neutral (30-70)**:
  - Mercado en equilibrio
  - Sin señales claras de compra o venta
  - Observar otros indicadores para confirmación

## MACD (Convergencia/Divergencia de Medias Móviles) 📊

### ¿Qué es?
El MACD es un indicador de momentum que muestra la relación entre dos medias móviles exponenciales.

### Cálculo
- Línea MACD = EMA(12) - EMA(26)
- Línea de Señal = EMA(9) de la línea MACD
- Histograma = Línea MACD - Línea de Señal

### Interpretación
- **MACD > Señal**:
  - Momentum alcista
  - Señal de compra potencial
  - Confirmación de tendencia alcista
- **MACD < Señal**:
  - Momentum bajista
  - Señal de venta potencial
  - Confirmación de tendencia bajista
- **Cruces**:
  - Cruce alcista: MACD cruza por encima de la señal
  - Cruce bajista: MACD cruza por debajo de la señal

## Bandas de Bollinger 📉

### ¿Qué es?
Las Bandas de Bollinger son un indicador de volatilidad que consta de tres líneas:
- Banda Superior: SMA(20) + (2 × Desviación Estándar)
- Banda Media: SMA(20)
- Banda Inferior: SMA(20) - (2 × Desviación Estándar)

### Interpretación
- **Precio cerca de banda superior**:
  - Posible sobrecompra
  - Considerar tomar ganancias
  - Posible corrección a la baja
- **Precio cerca de banda inferior**:
  - Posible sobreventa
  - Considerar oportunidades de compra
  - Posible rebote al alza
- **Bandas estrechas**:
  - Baja volatilidad
  - Posible acumulación
  - Prepararse para posible movimiento fuerte
- **Bandas anchas**:
  - Alta volatilidad
  - Mercado activo
  - Posible cambio de tendencia

## Stochastic 📈

### ¿Qué es?
El Stochastic es un oscilador que compara el precio de cierre con el rango de precios durante un período específico.

### Cálculo
- %K = ((Cierre - Mínimo) / (Máximo - Mínimo)) × 100
- %D = Media móvil de 3 períodos de %K

### Interpretación
- **Sobrecompra (>80)**:
  - Posible corrección a la baja
  - Considerar tomar ganancias
  - Señal de venta potencial
- **Sobreventa (<20)**:
  - Posible rebote al alza
  - Considerar oportunidades de compra
  - Señal de compra potencial
- **Zona Neutral (20-80)**:
  - Sin señales claras
  - Observar otros indicadores
  - Mercado en equilibrio

## Momentum 📊

### ¿Qué es?
El Momentum mide la velocidad del cambio de precios, comparando el precio actual con el precio de hace N períodos.

### Cálculo
- Momentum = Precio Actual - Precio (N períodos atrás)
- Donde N típicamente es 10 períodos

### Interpretación
- **Momentum Positivo**:
  - Fuerza alcista
  - Confirmación de tendencia alcista
  - Señal de compra potencial
- **Momentum Negativo**:
  - Fuerza bajista
  - Confirmación de tendencia bajista
  - Señal de venta potencial
- **Momentum Cero**:
  - Mercado lateral
  - Sin dirección clara
  - Observar otros indicadores

## Volumen 📈

### ¿Qué es?
El Volumen mide la cantidad de acciones negociadas en un período determinado.

### Interpretación
- **Volumen Fuerte (>1.5x promedio)**:
  - Confirmación de movimiento
  - Mayor confianza en la señal
  - Posible inicio de tendencia
- **Volumen Moderado (1.2-1.5x promedio)**:
  - Movimiento normal
  - Confirmación parcial
  - Observar otros indicadores
- **Volumen Débil (<1.2x promedio)**:
  - Movimiento débil
  - Baja confianza en la señal
  - Posible falta de interés

## Medias Móviles 📊

### Tipos
1. **SMA (Simple Moving Average)**
   - Media aritmética de N períodos
   - Más suave, menos reactiva
   - Mejor para tendencias largas

2. **EMA (Exponential Moving Average)**
   - Da más peso a precios recientes
   - Más reactiva a cambios
   - Mejor para señales tempranas

### Interpretación
- **Corto Plazo (SMA/EMA 20)**:
  - Tendencia inmediata
  - Señales de trading diario
  - Movimientos rápidos
- **Medio Plazo (SMA/EMA 50)**:
  - Tendencia intermedia
  - Confirmación de movimientos
  - Filtro de tendencia
- **Largo Plazo (SMA/EMA 200)**:
  - Tendencia principal
  - Filtro de mercado
  - Señal de mercado alcista/bajista

### Cruces Importantes
- **Cruce Dorado**: SMA/EMA 50 cruza por encima de SMA/EMA 200
  - Señal alcista fuerte
  - Confirmación de tendencia alcista
- **Cruce de la Muerte**: SMA/EMA 50 cruza por debajo de SMA/EMA 200
  - Señal bajista fuerte
  - Confirmación de tendencia bajista 