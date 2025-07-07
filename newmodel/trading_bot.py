import os
import logging
from datetime import datetime
from typing import Dict, List
import pandas as pd
import numpy as np
import yfinance as yf
import talib

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'results')
os.makedirs(RESULTS_DIR, exist_ok=True)

# --- Funciones de indicadores robustas (replican manejo de errores de investment_recommendations.py) ---
def calcular_indicadores(df: pd.DataFrame) -> Dict:
    res = {}
    try:
        close = df['Close'].astype(float).to_numpy().flatten()
        high = df['High'].astype(float).to_numpy().flatten()
        low = df['Low'].astype(float).to_numpy().flatten()
        volume = df['Volume'].astype(float).to_numpy().flatten()
        # EMAs
        for period in [9, 20, 50, 100, 200]:
            try:
                res[f'ema_{period}'] = float(pd.Series(close).ewm(span=period, adjust=False).mean().iloc[-1])
            except Exception as e:
                logging.warning(f'EMA{period} error: {e}')
                res[f'ema_{period}'] = np.nan
        # RSI
        try:
            rsi = talib.RSI(close, timeperiod=14)
            rsi = rsi[~np.isnan(rsi)]
            res['rsi'] = float(rsi[-1]) if len(rsi) else np.nan
        except Exception as e:
            logging.warning(f'RSI error: {e}')
            res['rsi'] = np.nan
        # ATR
        try:
            atr = talib.ATR(high, low, close, timeperiod=14)
            atr = atr[~np.isnan(atr)]
            res['atr'] = float(atr[-1]) if len(atr) else np.nan
        except Exception as e:
            logging.warning(f'ATR error: {e}')
            res['atr'] = np.nan
        # ADX
        try:
            adx = talib.ADX(high, low, close, timeperiod=14)
            adx = adx[~np.isnan(adx)]
            res['adx'] = float(adx[-1]) if len(adx) else np.nan
        except Exception as e:
            logging.warning(f'ADX error: {e}')
            res['adx'] = np.nan
        # MACD
        try:
            macd, macdsignal, macdhist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
            macd = macd[~np.isnan(macd)]
            macdsignal = macdsignal[~np.isnan(macdsignal)]
            res['macd'] = float(macd[-1]) if len(macd) else np.nan
            res['macd_signal'] = float(macdsignal[-1]) if len(macdsignal) else np.nan
        except Exception as e:
            logging.warning(f'MACD error: {e}')
            res['macd'] = np.nan
            res['macd_signal'] = np.nan
        # Bollinger Bands
        try:
            upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
            upper = upper[~np.isnan(upper)]
            lower = lower[~np.isnan(lower)]
            res['bb_upper'] = float(upper[-1]) if len(upper) else np.nan
            res['bb_lower'] = float(lower[-1]) if len(lower) else np.nan
        except Exception as e:
            logging.warning(f'Bollinger Bands error: {e}')
            res['bb_upper'] = np.nan
            res['bb_lower'] = np.nan
        # Stochastic Oscillator
        try:
            slowk, slowd = talib.STOCH(high, low, close, fastk_period=14, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
            slowk = slowk[~np.isnan(slowk)]
            slowd = slowd[~np.isnan(slowd)]
            res['stoch_k'] = float(slowk[-1]) if len(slowk) else np.nan
            res['stoch_d'] = float(slowd[-1]) if len(slowd) else np.nan
        except Exception as e:
            logging.warning(f'Stochastic error: {e}')
            res['stoch_k'] = np.nan
            res['stoch_d'] = np.nan
        # Volumen
        try:
            vol_20 = pd.Series(volume).rolling(window=20).mean().iloc[-1]
            res['vol_20'] = float(vol_20)
        except Exception as e:
            logging.warning(f'Volumen error: {e}')
            res['vol_20'] = np.nan
    except Exception as e:
        logging.error(f'Error general en indicadores: {e}')
    return res

# --- Supertrend ---
def calcular_supertrend(df: pd.DataFrame, period=10, multiplier=3) -> List[str]:
    # Implementación simple, robusta, sin fallback
    try:
        # Convertir a numpy arrays
        high = df['High'].astype(float).to_numpy()
        low = df['Low'].astype(float).to_numpy()
        close = df['Close'].astype(float).to_numpy()
        
        # Calcular ATR
        atr = talib.ATR(high, low, close, timeperiod=period)
        atr = pd.Series(atr, index=df.index)
        
        # Calcular bandas
        hl2 = (high + low) / 2
        final_upperband = hl2 + (multiplier * atr)
        final_lowerband = hl2 - (multiplier * atr)
        
        supertrend = [None] * len(df)
        direction = [None] * len(df)
        
        for i in range(period, len(df)):
            if i == period:
                supertrend[i] = final_upperband[i]
                direction[i] = 'red'
            else:
                if close[i] > final_upperband[i-1]:
                    supertrend[i] = final_lowerband[i]
                    direction[i] = 'green'
                elif close[i] < final_lowerband[i-1]:
                    supertrend[i] = final_upperband[i]
                    direction[i] = 'red'
                else:
                    supertrend[i] = supertrend[i-1]
                    direction[i] = direction[i-1]
        return direction
    except Exception as e:
        logging.warning(f'Supertrend error: {e}')
        return [None] * len(df)

# --- Señales por vela ---
def analizar_vela(df: pd.DataFrame, idx: int, supertrend: List[str], indicadores: Dict) -> Dict:
    res = {'datetime': df.index[idx], 'signal': 'NEUTRA', 'indicadores': []}
    try:
        # Convertir todos los valores a escalares
        ema9 = float(indicadores['ema_9'])
        ema20 = float(indicadores['ema_20'])
        ema200 = float(indicadores['ema_200'])
        rsi = float(indicadores['rsi'])
        adx = float(indicadores['adx'])
        macd = float(indicadores['macd'])
        macd_signal = float(indicadores['macd_signal'])
        bb_upper = float(indicadores['bb_upper'])
        bb_lower = float(indicadores['bb_lower'])
        stoch_k = float(indicadores['stoch_k'])
        stoch_d = float(indicadores['stoch_d'])
        close = float(df['Close'].iloc[idx].iloc[0] if isinstance(df['Close'].iloc[idx], pd.Series) else df['Close'].iloc[idx])

        # Supertrend
        st_color = supertrend[idx]

        # Pendiente EMA200
        ema200_prev = float(indicadores.get('ema_200_prev', ema200))
        ema200_slope = ema200 - ema200_prev

        # Cruce EMAs
        if ema9 > ema20 and rsi > 50 and st_color == 'green' and adx > 25 and ema200_slope > 0:
            res['signal'] = 'COMPRA'
            res['indicadores'] += ['EMA9>EMA20', 'RSI>50', 'Supertrend verde', 'ADX>25', 'EMA200 ascendente']
        elif ema9 < ema20 and rsi < 50 and st_color == 'red' and adx > 25 and ema200_slope < 0:
            res['signal'] = 'VENTA'
            res['indicadores'] += ['EMA9<EMA20', 'RSI<50', 'Supertrend rojo', 'ADX>25', 'EMA200 descendente']

        # MACD
        if macd > macd_signal:
            res['indicadores'].append('MACD cruce alcista')
        elif macd < macd_signal:
            res['indicadores'].append('MACD cruce bajista')

        # Bollinger
        if close > bb_upper:
            res['indicadores'].append('Ruptura banda superior BB')
        elif close < bb_lower:
            res['indicadores'].append('Ruptura banda inferior BB')

        # Stochastic
        if stoch_k < 20 and stoch_k > stoch_d:
            res['indicadores'].append('Stoch K cruza D en sobreventa')
        elif stoch_k > 80 and stoch_k < stoch_d:
            res['indicadores'].append('Stoch K cruza D en sobrecompra')

        # Reglas de salida
        atr = float(indicadores['atr'])
        if rsi > 70 or rsi < 30:
            res['indicadores'].append('RSI extremo')
        if idx > 0 and supertrend[idx] != supertrend[idx-1]:
            res['indicadores'].append('Cambio de Supertrend')

        # Take profit/stop loss dinámico (solo referencia, no ejecución)
        res['take_profit'] = close + 1.5 * atr if res['signal'] == 'COMPRA' else close - 1.5 * atr
        res['stop_loss'] = close - 1 * atr if res['signal'] == 'COMPRA' else close + 1 * atr

    except Exception as e:
        logging.warning(f'Error analizando vela: {e}')
    return res

# --- Main ---
def main(tickers: Dict[str, str]):
    for symbol, yf_symbol in tickers.items():
        logging.info(f'Analizando {symbol}...')
        try:
            df = yf.download(yf_symbol, period='30d', interval='1h', progress=False)
            if df.empty or len(df) < 50:
                logging.warning(f'Datos insuficientes para {symbol}')
                continue
            df = df.dropna()
            supertrend = calcular_supertrend(df)
            resultados = []
            for i in range(1, len(df)):
                indicadores = calcular_indicadores(df.iloc[:i+1])
                if i > 1:
                    indicadores['ema_200_prev'] = calcular_indicadores(df.iloc[:i])['ema_200']
                res = analizar_vela(df, i, supertrend, indicadores)
                resultados.append(res)
            # Guardar resultados
            df_result = pd.DataFrame(resultados)
            fname = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            df_result.to_csv(os.path.join(RESULTS_DIR, f'{fname}.csv'), index=False)
            df_result.to_json(os.path.join(RESULTS_DIR, f'{fname}.json'), orient='records', force_ascii=False)
            logging.info(f'Resultados guardados para {symbol}')
        except Exception as e:
            logging.error(f'Error en {symbol}: {e}')

if __name__ == '__main__':
    # Ejemplo de uso: el usuario debe pasar tickers reales
    # tickers = {'AAPL': 'AAPL', 'MSFT': 'MSFT'}
    tickers = {"AAPL":"AAPL"
    #            ,   # Apple Inc.
    # "PLTR":"PLTR",   # Palantir Technologies
    # "QQQ":"QQQ",    # Invesco QQQ Trust
    # "SPY":"SPY",    # SPDR S&P 500 ETF
    # "TSLA":"TSLA",   # Tesla Inc.
    # "NVDA":"NVDA",   # NVIDIA Corporation
    # "NU":"NU",     # Nu Holdings
    # "NIO":"NIO",    # Nio Inc.
    # "BABA":"BABA",   # Alibaba Group
    # "TSM":"TSM",    # Taiwan Semiconductor
    # "AMZN":"AMZN",   # Amazon.com Inc.
    # "GOOGL":"GOOGL",  # Alphabet Inc.
    # "JPM":"JPM",    # JPMorgan Chase
    # "COIN":"COIN",   # Coinbase Global
    # "META":"META",   # Meta Platforms
    # "MELI":"MELI",
    # "SNOW":"SNOW"
    }
    # tickers = {}  # El usuario debe completar esto
    if not tickers:
        logging.error('Debes proporcionar un diccionario de tickers reales. Ejemplo: {"AAPL": "AAPL"}')
    else:
        main(tickers) 