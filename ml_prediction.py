import pandas as pd
import numpy as np
from typing import Dict, Tuple

def validar_datos(data: pd.DataFrame) -> bool:
    """
    Valida que los datos tengan las columnas necesarias y suficientes datos
    """
    if data is None or data.empty:
        return False
    
    required_columns = ['Close', 'Volume']
    if not all(col in data.columns for col in required_columns):
        return False
    
    if len(data) < 20:  # Necesitamos al menos 20 días de datos
        return False
    
    return True

def calcular_volatilidad(data: pd.DataFrame) -> pd.Series:
    """
    Calcula la volatilidad histórica
    """
    returns = data['Close'].pct_change()
    return returns.rolling(window=20).std() * np.sqrt(252) * 100

def calcular_volumen_promedio(data: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Calcula el volumen promedio en una ventana móvil
    """
    return data['Volume'].rolling(window=window).mean()

def calcular_tendencia(data: pd.DataFrame) -> float:
    """
    Calcula la fuerza de la tendencia usando regresión lineal
    """
    x = np.arange(len(data))
    y = data['Close'].values
    slope, _ = np.polyfit(x, y, 1)
    return slope

def predecir_direccion(data: pd.DataFrame) -> Tuple[str, float]:
    """
    Predice la dirección del precio y calcula un score de confianza
    """
    if not validar_datos(data):
        return "error", 0.0
    
    try:
        # Obtener últimos precios
        ultimo_precio = data["Close"].iloc[-1].item()
        precio_anterior = data["Close"].iloc[-2].item()
        
        # Calcular cambio de precio
        cambio_precio = ((ultimo_precio - precio_anterior) / precio_anterior) * 100
        
        # Calcular tendencias
        tendencia_corta = data['Close'].pct_change(periods=5).iloc[-1].item() * 100
        tendencia_media = data['Close'].pct_change(periods=20).iloc[-1].item() * 100
        
        # Calcular volumen
        volumen_actual = data['Volume'].iloc[-1].item()
        volumen_promedio = calcular_volumen_promedio(data).iloc[-1].item()
        ratio_volumen = volumen_actual / volumen_promedio if volumen_promedio > 0 else 1.0
        
        # Calcular volatilidad
        current_vol = calcular_volatilidad(data).iloc[-1].item()
        prev_vol = calcular_volatilidad(data).iloc[-5].item()
        vol_trend = current_vol - prev_vol
        
        # Determinar dirección y score de tendencia
        if tendencia_corta > 0 and tendencia_media > 0:
            direccion = "sube"
            trend_score = 3
        elif tendencia_corta < 0 and tendencia_media < 0:
            direccion = "baja"
            trend_score = 3
        elif tendencia_corta > 0:
            direccion = "sube"
            trend_score = 2
        elif tendencia_corta < 0:
            direccion = "baja"
            trend_score = 2
        else:
            direccion = "mantener"
            trend_score = 1
        
        # Calcular score de confianza
        price_strength = min(abs(cambio_precio) / 1.5, 1.0)  # Más sensible
        volume_ratio = min(ratio_volumen / 1.5, 1.0)         # Más sensible
        
        # Penalización suavizada por volatilidad
        if current_vol < 15:
            volatility_factor = 1.0
        elif current_vol < 30:
            volatility_factor = 0.9
        else:
            volatility_factor = 0.8
        
        trend_factor = trend_score / 3
        
        # Calcular confianza final
        confianza = (
            price_strength * 0.35 +   # 35% peso al cambio de precio
            volume_ratio * 0.25 +     # 25% peso al volumen
            volatility_factor * 0.15 + # 15% peso a la volatilidad
            trend_factor * 0.25       # 25% peso a la tendencia
        )
        
        # Multiplicador para tendencias fuertes
        if trend_score == 3:
            confianza *= 1.10  # +10% para tendencias muy fuertes
        elif trend_score == 2:
            confianza *= 1.05  # +5% para tendencias moderadas
        
        # Limitar confianza entre 0.7 y 0.99
        confianza = max(0.7, min(0.99, confianza))
        
        # Agregar contexto a la predicción
        if direccion == "sube":
            prediccion = f"sube (tendencia alcista {trend_score}/3)"
        elif direccion == "baja":
            prediccion = f"baja (tendencia bajista {trend_score}/3)"
        else:
            prediccion = "mantener (tendencia lateral)"
        
        return prediccion, confianza
        
    except Exception as e:
        print(f"Error en predicción: {str(e)}")
        return "error", 0.0