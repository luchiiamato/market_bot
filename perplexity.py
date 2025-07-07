import yfinance as yf
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime
import json
import talib
from multiprocessing import Pool
import warnings
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import shap

warnings.filterwarnings("ignore", message="YF.download.*")

# Configuration
MODEL_PARAMS = {
    'n_estimators': 200,
    'max_depth': 8,
    'random_state': 42,
    'class_weight': 'balanced'
}

FEATURE_WEIGHTS = {
    'ml_probability': 0.5,
    'technical': 0.5
}

CEDEAR_MAPPING = {
    'TMUS':'TMUS',
    'LLY':'LLY',
    "YPF":"YPF",
    "AAPL":"AAPL", 
    "PLTR":"PLTR", 
    "QQQ":"QQQ",  
    "SPY":"SPY",  
    "TSLA":"TSLA", 
    "NVDA":"NVDA", 
    "NU":"NU",   
    "NIO":"NIO",  
    "BABA":"BABA", 
    "TSM":"TSM",  
    "AMZN":"AMZN", 
    "GOOGL":"GOOGL",
    "COIN":"COIN",
    "JPM":"JPM",
    "META":"META", 
    "AMD":"AMD", 
    "MELI":"MELI",
    "LLY":"LLY",
    "PFE":"PFE",
    "MRK":"MRK",
   'SATL': 'SATL',   
   'AAPL': 'AAPL',   # Apple Inc.
   'MSFT': 'MSFT',   # Microsoft Corporation
   'AMZN': 'AMZN',   # Amazon.com, Inc.
   'GOOGL': 'GOOGL', # Alphabet Inc. (Google)
   'META': 'META',   # Meta Platforms, Inc. (Facebook)
   'TSLA': 'TSLA',   # Tesla, Inc.
   'NVDA': 'NVDA',   # NVIDIA Corporation
   'JPM': 'JPM',     # JPMorgan Chase & Co.
   'V': 'V',         # Visa Inc.
   'WMT': 'WMT',     # Walmart Inc.
   'DIS': 'DIS',     # The Walt Disney Company
   'NFLX': 'NFLX',   # Netflix, Inc.
   'PYPL': 'PYPL',   # PayPal Holdings, Inc.
   'INTC': 'INTC',   # Intel Corporation
   'AMD': 'AMD',     # Advanced Micro Devices, Inc.
   'CSCO': 'CSCO',   # Cisco Systems, Inc.
   'ORCL': 'ORCL',   # Oracle Corporation
   'IBM': 'IBM',     # International Business Machines Corporation
   'CRM': 'CRM',     # Salesforce, Inc.
   'ADBE': 'ADBE',   # Adobe Inc.
   'KO': 'KO',       # The Coca-Cola Company
   'PEP': 'PEP',     # PepsiCo, Inc.
   'MCD': 'MCD',     # McDonald's Corporation
   'BA': 'BA',       # The Boeing Company
   'GE': 'GE',       # General Electric Company
   'BABA': 'BABA',   # Alibaba Group Holding Limited
   'NKE': 'NKE',     # NIKE, Inc.
   'PFE': 'PFE',     # Pfizer Inc.
   'JNJ': 'JNJ',     # Johnson & Johnson
   'LLY': 'LLY',     # Eli Lilly and Company
   'MRK': 'MRK',     # Merck & Co., Inc.
   'XOM': 'XOM',     # Exxon Mobil Corporation
   'CVX': 'CVX',     # Chevron Corporation
   'T': 'T',         # AT&T Inc.
   'VZ': 'VZ',       # Verizon Communications Inc.
   'SNE': 'SONY',    # Sony Group Corporation
   'FDX': 'FDX',     # FedEx Corporation
   'UPS': 'UPS',     # United Parcel Service, Inc.
   'C': 'C',         # Citigroup Inc.
   'BAC': 'BAC',     # Bank of America Corporation
   'GS': 'GS',       # The Goldman Sachs Group, Inc.
   'AXP': 'AXP',     # American Express Company
   'BRK.B': 'BRK.B', # Berkshire Hathaway Inc. Class B
   'GILD': 'GILD',   # Gilead Sciences, Inc.
   'AMGN': 'AMGN',   # Amgen Inc.
   'BIIB': 'BIIB',   # Biogen Inc.
   'ABBV': 'ABBV',   # AbbVie Inc.
   'BMY': 'BMY',     # Bristol-Myers Squibb Company
   'AZN': 'AZN',     # AstraZeneca PLC
   'GSK': 'GSK',     # GlaxoSmithKline plc
   'SNY': 'SNY',     # Sanofi
   'RIO': 'RIO',     # Rio Tinto Group
   'VALE': 'VALE',   # Vale S.A.
   'BHP': 'BHP',     # BHP Group Limited
   'SLB': 'SLB',     # Schlumberger Limited
   'TOT': 'TTE',     # TotalEnergies SE
   'BP': 'BP',       # BP p.l.c.
   'E': 'E',         # Eni S.p.A.
   'PTR': 'PTR',     # PetroChina Company Limited
   'LMT': 'LMT',     # Lockheed Martin Corporation
   'HON': 'HON',     # Honeywell International Inc.
   'MMM': 'MMM',     # 3M Company
   'CAT': 'CAT',     # Caterpillar Inc.
   'DE': 'DE',       # Deere & Company
   'DHR': 'DHR',     # Danaher Corporation
   'ADP': 'ADP',     # Automatic Data Processing, Inc.
   'AVGO': 'AVGO',   # Broadcom Inc.
   'QCOM': 'QCOM',   # QUALCOMM Incorporated
   'TXN': 'TXN',     # Texas Instruments Incorporated
   'MU': 'MU',       # Micron Technology, Inc.
   'LRCX': 'LRCX',   # Lam Research Corporation
   'AMAT': 'AMAT',   # Applied Materials, Inc.
   'INTU': 'INTU',   # Intuit Inc.
   'NOW': 'NOW',     # ServiceNow, Inc.
   'SHOP': 'SHOP',   # Shopify Inc.
   'SQ': 'SQ',       # Block, Inc. (formerly Square, Inc.)
   'UBER': 'UBER',   # Uber Technologies, Inc.
   'LYFT': 'LYFT',   # Lyft, Inc.
   'ZM': 'ZM',       # Zoom Video Communications, Inc.
   'DOCU': 'DOCU',   # DocuSign, Inc.
   'ETSY': 'ETSY',   # Etsy, Inc.
   'ROKU': 'ROKU',   # Roku, Inc.
   'SPOT': 'SPOT',   # Spotify Technology S.A.
   'NET': 'NET',     # Cloudflare, Inc.
   'CRWD': 'CRWD',   # CrowdStrike Holdings, Inc.SNOW
   'OKTA': 'OKTA',   # Okta, Inc.
   'ZS': 'ZS',       # Zscaler, Inc.
   'PANW': 'PANW',   # Palo Alto Networks, Inc.
   'SPLK': 'SPLK',   # Splunk Inc.
   'DDOG': 'DDOG',   # Datadog, Inc.
   'FSLY': 'FSLY',   # Fastly, Inc.
   'MDB': 'MDB',     # MongoDB, Inc.
   'SNOW': 'SNOW',   # Snowflake Inc.
   'U': 'U',         # Unity Software Inc.
   'PLTR': 'PLTR',   # Palantir Technologies Inc.
   'RBLX': 'RBLX',   # Roblox Corporation
   'BIDU': 'BIDU'
}

class StockPredictor:
    def __init__(self):
        self.models = {}
        self.explainers = {}
        
    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for ML model"""
        
        if data.empty:
            return None
        data.dropna(inplace=True)
        if any(len(data[c].dropna()) < 200 for c in ['Close', 'High', 'Low', 'Volume']):
            return None

        closes = data['Close'].dropna().astype(float).to_numpy().flatten()
        highs = data['High'].dropna().astype(float).to_numpy().flatten()
        lows = data['Low'].dropna().astype(float).to_numpy().flatten()
        volume = data['Volume'].dropna().astype(float).to_numpy().flatten()
        
        features = pd.DataFrame(index=data.index)
        features['sma_20'] = talib.SMA(closes, 20)
        features['ema_12'] = talib.EMA(closes, 12)
        features['rsi'] = talib.RSI(closes, 14)
        features['macd'], features['macd_signal'], _ = talib.MACD(closes)
        features['atr'] = talib.ATR(highs, lows, closes, 14)
        features['adx'] = talib.ADX(highs, lows, closes, 14)
        features['cci'] = talib.CCI(highs, lows, closes, 20)
        features['volume_change'] = data['Volume'].pct_change()
        features['close_pct_change'] = data['Close'].pct_change()
        features['target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        return features.dropna()

    def train_model(self, ticker: str):
        """Train model for specific ticker"""
        try:
            data = yf.download(ticker, period="5y", interval="1d")
            print(f"Training model for {ticker}")
            features = self.prepare_features(data)
            
            X = features.drop('target', axis=1)
            y = features['target']

            # Handle infinity and large values
            X = X.replace([np.inf, -np.inf], np.nan)
            X = X.fillna(X.mean())  # Replace NaN with mean values
            
            # Ensure all values are within float32 range
            X = np.clip(X, -1e38, 1e38)  # Clip to safe float32 range
            
            # Time-based split
            split_idx = int(len(X) * 0.8)
            X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
            
            model = RandomForestClassifier(**MODEL_PARAMS)
            model.fit(X_train, y_train)
            
            # Generate SHAP explainer
            explainer = shap.TreeExplainer(model)
            self.models[ticker] = model
            self.explainers[ticker] = explainer
            
            return model.score(X_test, y_test)
        except Exception as e:
            print(f"Error training model for {ticker}: {str(e)}")
            return None

    def predict_proba(self, ticker: str, latest_data: pd.DataFrame) -> float:
        """Get prediction probability for latest data"""
        if ticker not in self.models:
            self.train_model(ticker)
        print(f"Predicting probability for {ticker}")
        features = self.prepare_features(latest_data)
        if features.empty:
            return 0.5  # Neutral probability if insufficient data
            
        latest_features = features.iloc[[-1]].drop('target', axis=1, errors='ignore')
        return self.models[ticker].predict_proba(latest_features)[0][1]

def enhanced_calcular_metricas_cedear(ticker: str, predictor: StockPredictor) -> Dict:
    """Enhanced version with ML predictions"""
    data = yf.download(ticker, period="1y", interval="1d")
    if len(data) < 30:  # Minimum data check
        return None
        
    # Existing technical analysis
    metricas = calcular_metricas_cedear(ticker)
    if metricas is None:
        return None
        
    # ML Prediction
    ml_prob = predictor.predict_proba(ticker, data)
    print(f"ML Probability: {ml_prob}")
    metricas['ml_probability'] = ml_prob

    return metricas

def enhanced_calcular_score_inversion(metricas: Dict) -> Tuple[float, List[str]]:
    """Enhanced scoring with ML weights"""
    score = 0
    razones = []
    
    # ML Component
    ml_score = metricas['ml_probability'] * 100 * FEATURE_WEIGHTS['ml_probability']
    score += ml_score
    razones.append(f"ML Probability: {metricas['ml_probability']:.2f}")
    
    # Technical Components (adjusted weights)
    tech_score, tech_razones = original_calcular_score_inversion(metricas)
    score += tech_score * FEATURE_WEIGHTS['technical']
    razones.extend(tech_razones)
    
    return round(score, 2), razones

def generar_reporte_con_ml(capital: float = 10000):
    """Generate report with ML integration"""
    predictor = StockPredictor()
    
    with Pool(processes=4) as pool:
        metricas_todos = []
        for ticker in CEDEAR_MAPPING:
            metricas = enhanced_calcular_metricas_cedear(ticker, predictor)
            if metricas:
                metricas_todos.append(metricas)
    
    # Rest of your existing recommendation logic
    recomendaciones = []
    for m in metricas_todos:
        score, razones = enhanced_calcular_score_inversion(m)
        acciones = int(capital / m['precio'])
        inversion_total = acciones * m['precio']
        technical_prob = np.clip(score / 100, 0, 1)
        ml_prob = metricas.get('ml_probability', 0.5)  # fallback to 0.5 if missing

        # prob_suba = 0.5 * ml_prob + 0.5 * technical_prob
        prob_suba = 0.7 * ml_prob + 0.3 * technical_prob
        prob_baja = 1 - prob_suba
        upside_factor = 2.5
        downside_factor = 1.5
        expected_return = (prob_suba * m['atr'] * upside_factor) - (prob_baja * m['atr'] * downside_factor)
        potencial_ganancia = expected_return * acciones

        recomendaciones.append({
            'ticker': m['ticker'],
            'precio_actual': round(m['precio'], 2),
            'score': score,
            'acciones_recomendadas': acciones,
            'inversion_total': round(inversion_total, 2),
            'potencial_ganancia': round(potencial_ganancia, 2),
            'rsi': round(m['rsi'], 2),
            'tendencia_larga': m['tendencia_larga'],
            'razones': razones
        })

    recomendaciones.sort(key=lambda x: ( -x['score'],-x['potencial_ganancia']))
    return recomendaciones[:100]
        
    # Generate SHAP explanation plot
    for ticker in CEDEAR_MAPPING:
        if ticker in predictor.explainers:
            data = yf.download(ticker, period="1y", interval="1d")
            features = predictor.prepare_features(data)
            shap_values = predictor.explainers[ticker].shap_values(features.drop('target', axis=1))
            shap.summary_plot(shap_values, features, show=False)
            plt.savefig(f'shap_{ticker}_{datetime.now().strftime("%Y%m%d")}.png')
            plt.close()
    
    # ... rest of your existing report generation logic

# Replace original functions while keeping compatibility 
def original_calcular_score_inversion(metricas: Dict):
    score = 0
    razones = []
    peso = {
        'tendencia': 0.2, 'rsi': 0.1, 'macd': 0.1, 'bb': 0.1,
        'volumen': 0.1, 'stochastic': 0.1, 'momentum': 0.1,
        'soportes': 0.05, 'adx': 0.05, 'atr': 0.05, 'cci': 0.05
    }
    score += metricas['fuerza_tendencia'] * 10 * peso['tendencia']
    razones.append(f"Fuerza tendencia: {metricas['fuerza_tendencia']}/3")
    score += (15 if metricas['rsi'] < 30 else 5 if metricas['rsi'] > 70 else 10) * peso['rsi']
    razones.append(f"RSI: {metricas['rsi']:.1f}")
    score += (15 if metricas['macd'] > metricas['macd_signal'] else 5) * peso['macd']
    razones.append("MACD positivo" if metricas['macd'] > metricas['macd_signal'] else "MACD negativo")
    score += (15 if metricas['precio'] < metricas['bb_lower'] else 5 if metricas['precio'] > metricas['bb_upper'] else 10) * peso['bb']
    razones.append(f"Bandas de Bollinger (precio actual: {metricas['precio']:.2f})")
    score += (15 if metricas['ratio_volumen'] > 1.5 else 10 if metricas['ratio_volumen'] > 1.2 else 5) * peso['volumen']
    razones.append(f"Volumen x{metricas['ratio_volumen']:.2f}")
    score += (15 if metricas['stoch_k'] < 20 and metricas['stoch_d'] < 20 else 5 if metricas['stoch_k'] > 80 else 10) * peso['stochastic']
    razones.append(f"Stochastic K: {metricas['stoch_k']:.1f}, D: {metricas['stoch_d']:.1f}")
    score += (15 if metricas['momentum'] > 0 else 5) * peso['momentum']
    razones.append(f"Momentum: {'positivo' if metricas['momentum'] > 0 else 'negativo'}")
    score += (15 if metricas['soporte_cercano'] else 5 if metricas['resistencia_cercana'] else 10) * peso['soportes']
    razones.append("Cerca de soporte" if metricas['soporte_cercano'] else "Cerca de resistencia" if metricas['resistencia_cercana'] else "Neutral técnico")
    score += (15 if metricas['adx'] >= 25 else 5) * peso['adx']
    razones.append(f"ADX: {metricas['adx']:.1f}")
    score += (15 if metricas['atr'] > metricas['precio'] * 0.02 else 5) * peso['atr']
    razones.append(f"ATR: {metricas['atr']:.2f}")
    score += (15 if metricas['cci'] < -100 else 5 if metricas['cci'] > 100 else 10) * peso['cci']
    razones.append(f"CCI: {metricas['cci']:.1f}")
    return round(score, 2), razones
    # ... your original scoring implementation ...
    # (Keep this unchanged from your initial code)


def get_support_resistance(data: pd.DataFrame) -> Tuple[bool, bool]:
    closes = data['Close'].astype(float)
    last_price = float(closes.iloc[-1])
    supports = closes[(closes.shift(2) > closes.shift(1)) & (closes.shift(1) < closes)]
    resistances = closes[(closes.shift(2) < closes.shift(1)) & (closes.shift(1) > closes)]
    supports = supports.astype(float).values[-10:]
    resistances = resistances.astype(float).values[-10:]
    near_support = any(abs(last_price - float(s)) / last_price < 0.02 for s in supports)
    near_resistance = any(abs(last_price - float(r)) / last_price < 0.02 for r in resistances)
    return near_support, near_resistance

def calcular_metricas_cedear(ticker: str):
    data = yf.download(ticker, period="5y", interval="1d")
    if data.empty:
        return None
    data.dropna(inplace=True)
    if any(len(data[c].dropna()) < 200 for c in ['Close', 'High', 'Low', 'Volume']):
        return None

    close = data['Close'].dropna().astype(float).to_numpy().flatten()
    high = data['High'].dropna().astype(float).to_numpy().flatten()
    low = data['Low'].dropna().astype(float).to_numpy().flatten()
    volume = data['Volume'].dropna().astype(float).to_numpy().flatten()

    precio_actual = close[-1]
    precio_anterior = close[-2]
    cambio_diario = ((precio_actual - precio_anterior) / precio_anterior) * 100
    print(f"Cambio diario: {cambio_diario}")
    sma_20 = talib.SMA(close, 20)[-1]
    print(f"SMA 20: {sma_20}")
    sma_50 = talib.SMA(close, 50)[-1]
    print(f"SMA 50: {sma_50}")
    sma_200 = talib.SMA(close, 200)[-1]
    print(f"SMA 200: {sma_200}")
    ema_12 = talib.EMA(close, 12)[-1]
    ema_26 = talib.EMA(close, 26)[-1]
    rsi = talib.RSI(close, 14)[-1]
    macd, macd_signal, _ = talib.MACD(close)
    bb_upper, bb_middle, bb_lower = talib.BBANDS(close, 20)
    ratio_volumen = volume[-1] / np.mean(volume[-20:])
    atr = talib.ATR(high, low, close, 14)[-1]
    slowk, slowd = talib.STOCH(high, low, close, 14, 3, 0, 3, 0)
    momentum = talib.MOM(close, 10)[-1]
    adx = talib.ADX(high, low, close, 14)[-1]
    cci = talib.CCI(high, low, close, 20)[-1]
    soporte, resistencia = get_support_resistance(data)

    tendencia_corta = "ALCISTA" if precio_actual > sma_20 else "BAJISTA"
    tendencia_media = "ALCISTA" if precio_actual > sma_50 else "BAJISTA"
    tendencia_larga = "ALCISTA" if precio_actual > sma_200 else "BAJISTA"
    fuerza_tendencia = sum([
        tendencia_corta == "ALCISTA",
        tendencia_media == "ALCISTA",
        tendencia_larga == "ALCISTA"
    ])
    print(f"Fuerza tendencia: {fuerza_tendencia}")
    return {
        'ticker': ticker,
        'precio': precio_actual,
        'cambio_diario': cambio_diario,
        'sma_20': sma_20,
        'sma_50': sma_50,
        'sma_200': sma_200,
        'ema_12': ema_12,
        'ema_26': ema_26,
        'rsi': rsi,
        'macd': macd[-1],
        'macd_signal': macd_signal[-1],
        'bb_upper': bb_upper[-1],
        'bb_middle': bb_middle[-1],
        'bb_lower': bb_lower[-1],
        'ratio_volumen': ratio_volumen,
        'atr': atr,
        'stoch_k': slowk[-1],
        'stoch_d': slowd[-1],
        'momentum': momentum,
        'adx': adx,
        'cci': cci,
        'soporte_cercano': soporte,
        'resistencia_cercana': resistencia,
        'tendencia_corta': tendencia_corta,
        'tendencia_media': tendencia_media,
        'tendencia_larga': tendencia_larga,
        'fuerza_tendencia': fuerza_tendencia,
    }
# Rest of your original functions remain unchanged

# if __name__ == "__main__":
#     generar_reporte_con_ml()
def generar_reporte_inversiones(capital: float = 10000):
    recomendaciones = generar_reporte_con_ml(capital)
    reporte = {
        "fecha_generacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "capital_disponible": capital,
        "recomendaciones": recomendaciones
    }
    nombre_archivo = f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(nombre_archivo, 'w') as f:
        json.dump(reporte, f, indent=2)
    print(f"Reporte generado: {nombre_archivo}")

if __name__ == "__main__":
    generar_reporte_inversiones()