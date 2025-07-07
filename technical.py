import pandas as pd
import numpy as np
from typing import Dict, Tuple, List, Union

def calcular_indicadores(data: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula indicadores técnicos para el análisis
    """
    try:
        # Calcular medias móviles
        data['SMA20'] = data['Close'].rolling(window=20).mean()
        data['SMA50'] = data['Close'].rolling(window=50).mean()
        data['SMA200'] = data['Close'].rolling(window=200).mean()
        
        # Calcular RSI
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        # Calcular MACD
        exp1 = data['Close'].ewm(span=12, adjust=False).mean()
        exp2 = data['Close'].ewm(span=26, adjust=False).mean()
        data['MACD'] = exp1 - exp2
        data['Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
        
        # Calcular Bollinger Bands
        data['BB_middle'] = data['Close'].rolling(window=20).mean()
        bb_std = data['Close'].rolling(window=20).std()
        if isinstance(bb_std, pd.DataFrame):
            bb_std = bb_std.iloc[:, 0]
        data['BB_upper'] = data['BB_middle'] + (bb_std * 2)
        data['BB_lower'] = data['BB_middle'] - (bb_std * 2)
        
        # Calcular ATR
        high_low = data['High'] - data['Low']
        high_close = np.abs(data['High'] - data['Close'].shift())
        low_close = np.abs(data['Low'] - data['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        data['ATR'] = true_range.rolling(14).mean()
        
        return data
        
    except Exception as e:
        print(f"Error calculando indicadores: {str(e)}")
        return None

def generar_senal_tecnica(data: pd.DataFrame) -> Dict:
    """
    Genera señales de trading basadas en indicadores técnicos
    """
    try:
        if data is None or data.empty:
            return None
            
        # Obtener últimos valores
        precio_actual = data["Close"].iloc[-1].item()
        sma20 = data["SMA20"].iloc[-1].item()
        sma50 = data["SMA50"].iloc[-1].item()
        sma200 = data["SMA200"].iloc[-1].item()
        rsi = data["RSI"].iloc[-1].item()
        macd = data["MACD"].iloc[-1].item()
        signal = data["Signal"].iloc[-1].item()
        bb_upper = data["BB_upper"].iloc[-1].item()
        bb_lower = data["BB_lower"].iloc[-1].item()
        atr = data["ATR"].iloc[-1].item()
        
        # Calcular fuerza de tendencia
        tendencia_fuerza = ((sma20 - sma50) / sma50) * 100
        
        # Inicializar variables
        senal = "mantener"
        razones = []
        score = 0
        
        # Análisis de tendencia
        if tendencia_fuerza > 1.0:
            razones.append(f"Media móvil de 20 días supera en {tendencia_fuerza:.1f}% a la de 50 días")
            score += 2
        elif tendencia_fuerza < -1.0:
            razones.append(f"Media móvil de 20 días está {abs(tendencia_fuerza):.1f}% por debajo de la de 50 días")
            score -= 2
        
        # Análisis RSI
        if rsi > 80:
            razones.append("RSI en sobrecompra extrema (>80), riesgo de corrección")
            score -= 2
        elif rsi > 70:
            razones.append("RSI en sobrecompra (>70), posible resistencia")
            score -= 1
        elif rsi < 20:
            razones.append("RSI en sobreventa extrema (<20), posible rebote")
            score += 2
        elif rsi < 30:
            razones.append("RSI en sobreventa (<30), posible soporte")
            score += 1
        
        # Análisis MACD
        if macd > signal:
            razones.append("MACD por encima de la señal, momentum alcista")
            score += 1
        else:
            razones.append("MACD por debajo de la señal, momentum bajista")
            score -= 1
        
        # Análisis Bollinger Bands
        if precio_actual > bb_upper:
            razones.append("Precio por encima de la banda superior de Bollinger")
            score -= 1
        elif precio_actual < bb_lower:
            razones.append("Precio por debajo de la banda inferior de Bollinger")
            score += 1
        
        # Determinar señal final
        if score >= 2:
            senal = "comprar"
        elif score <= -2:
            senal = "vender"
        
        # Calcular stop loss y take profit
        stop_loss = precio_actual - (2 * atr)
        take_profit = precio_actual + (3 * atr)
        
        return {
            "senal": senal,
            "razones": razones,
            "score": score,
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2)
        }
        
    except Exception as e:
        print(f"Error generando señal técnica: {str(e)}")
        return None

def calcular_sl_tp(data: pd.DataFrame) -> Tuple[float, float]:
    """
    Calculate dynamic stop loss and take profit levels based on volatility.
    
    Args:
        data (pd.DataFrame): DataFrame with price data
        
    Returns:
        Tuple[float, float]: Stop loss and take profit levels
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame")
    
    if 'Close' not in data.columns:
        raise ValueError("DataFrame must contain 'Close' column")
    
    precio_actual = float(data["Close"].iloc[-1])
    
    # Calculate ATR (Average True Range) for dynamic levels
    high_low = data['High'] - data['Low']
    high_close = np.abs(data['High'] - data['Close'].shift())
    low_close = np.abs(data['Low'] - data['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    atr = float(true_range.rolling(14).mean().iloc[-1])
    
    # Use ATR for dynamic levels (2x ATR for TP, 1x ATR for SL)
    sl = round(precio_actual - atr, 2)
    tp = round(precio_actual + (2 * atr), 2)
    
    return sl, tp