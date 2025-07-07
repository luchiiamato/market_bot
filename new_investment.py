import yfinance as yf
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime
import json
import talib
from multiprocessing import Pool
import warnings

warnings.filterwarnings("ignore", message="YF.download.*")

CEDEAR_MAPPING = {
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
    "JPM":"JPM",  
    "META":"META", 
    "MELI":"MELI",
    "SNOW":"SNOW",
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
    'CRWD': 'CRWD',   # CrowdStrike Holdings, Inc.
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
    'BIDU': 'BIDU',   # Baidu, Inc.
    'JD': 'JD',       # JD.com, Inc.
    'NTES': 'NTES',   # NetEase, Inc.
    'PDD': 'PDD',     # Pinduoduo Inc.
    'TCEHY': 'TCEHY', # Tencent Holdings Limited
    'MELI': 'MELI',   # MercadoLibre, Inc.
    'GLOB': 'GLOB',   # Globant S.A.
    'DESP': 'DESP',   # Despegar.com, Corp.
    'ARCO': 'ARCO',   # Arcos Dorados Holdings Inc.
    'VIST': 'VIST',   # Vista Oil & Gas, S.A.B. de C.V.
    'YPF': 'YPF',     # YPF S.A.
    'GGAL': 'GGAL',   # Grupo Financiero Galicia S.A.
    'BMA': 'BMA',     # Banco Macro S.A.
    'SUPV': 'SUPV',   # Grupo Supervielle S.A.
    'BBAR': 'BBAR',   # BBVA Argentina S.A.
    'TS': 'TS',       # Tenaris S.A.
    'TGS': 'TGS',     # Transportadora de Gas del Sur S.A.
    'PAM': 'PAM',     # Pampa Energía S.A.
    'CEPU': 'CEPU',   # Central Puerto S.A.
    'EDN': 'EDN',     # Empresa Distribuidora y Comercializadora Norte S.A.
    'LOMA': 'LOMA',   # Loma Negra Compañía Industrial Argentina S.A.
    'CRESY': 'CRESY', # Cresud S.A.C.I.F. y A.
    'AGRO': 'AGRO',   # Adecoagro S.A.
    'IRS': 'IRS',     # IRSA Inversiones y Representaciones Sociedad Anónima
    'IRCP': 'IRCP',   # IRSA Propiedades Comerciales S.A.
    'TGSU2': 'TGSU2', # Transportadora de Gas del Sur S.A.
    'BBVA': 'BBVA',   # Banco Bilbao Vizcaya Argentaria, S.A.
    'SAN': 'SAN',     # Banco Santander, S.A.
    'BBD': 'BBD',     # Banco Bradesco S.A.
    'BSBR': 'BSBR',   # Banco Santander (Brasil) S.A.
    'ITUB': 'ITUB',   # Itaú Unibanco Holding S.A.
    'VALE': 'VALE',   # Vale S.A.
    'PBR': 'PBR',     # Petróleo Brasileiro S.A. - Petrobras
    'ELET': 'ELET',   # Centrais Elétricas Brasileiras S.A.
    'CPLE6': 'CPLE6', # Companhia Paranaense de Energia - Copel
    'GGB': 'GGB',     # Gerdau S.A.
    'SID': 'SID',     # Companhia Siderúrgica Nacional
    'CSNA3': 'CSNA3', # Companhia Siderúrgica Nacional
    'USIM5': 'USIM5', # Usinas Siderúrgicas de Minas Gerais S.A.
    'BRFS': 'BRFS',   # BRF S.A.
    'ABEV': 'ABEV',   # Ambev S.A. - NASDAQ
    'ABT': 'ABT',     # Abbott Laboratories - NYSE
    'ABBV': 'ABBV',   # AbbVie Inc. - NYSE
    'ADBE': 'ADBE',   # Adobe Inc. - NASDAQ
    'ADGO': 'ADGO',   # Adecoagro S.A. - NYSE
    'ADI': 'ADI',     # Analog Devices, Inc. - NASDAQ
    'ADP': 'ADP',     # Automatic Data Processing, Inc. - NASDAQ
    'ADS': 'ADS',     # Adidas AG - XETRA
    'AEG': 'AEG',     # Aegon N.V. - NYSE
    'AEM': 'AEM',     # Agnico Eagle Mines Limited - NYSE
    'AIG': 'AIG',     # American International Group, Inc. - NYSE
    'AKO.B': 'AKO.B', # Embotelladora Andina S.A. - NYSE
    'AMAT': 'AMAT',   # Applied Materials, Inc. - NASDAQ
    'AMD': 'AMD',     # Advanced Micro Devices, Inc. - NASDAQ
    'AMGN': 'AMGN',   # Amgen Inc. - NASDAQ
    'AMX': 'AMX',     # América Móvil, S.A.B. de C.V. - NYSE
    'AMZN': 'AMZN',   # Amazon.com, Inc. - NASDAQ
    'ARCO': 'ARCO',   # Arcos Dorados Holdings Inc. - NYSE
    'ASML': 'ASML',   # ASML Holding N.V. - NASDAQ
    'AZN': 'AZN',     # AstraZeneca PLC - NYSE
    'BA': 'BA',       # The Boeing Company - NYSE
    'BAC': 'BAC',     # Bank of America Corporation - NYSE
    'BABA': 'BABA',   # Alibaba Group Holding Limited - NYSE
    'BBD': 'BBD',     # Banco Bradesco S.A. - NYSE
    'BBVA': 'BBVA',   # Banco Bilbao Vizcaya Argentaria, S.A. - NYSE
    'BHP': 'BHP',     # BHP Group Limited - NYSE
    'BIIB': 'BIIB',   # Biogen Inc. - NASDAQ
    'BMY': 'BMY',     # Bristol-Myers Squibb Company - NYSE
    'BP': 'BP',       # BP p.l.c. - NYSE
    'BRFS': 'BRFS',   # BRF S.A. - NYSE
    'BSBR': 'BSBR',   # Banco Santander (Brasil) S.A. - NYSE
    'C': 'C',         # Citigroup Inc. - NYSE
    'CAT': 'CAT',     # Caterpillar Inc. - NYSE
    'CCL': 'CCL',     # Carnival Corporation & plc - NYSE
    'CRM': 'CRM',     # Salesforce, Inc. - NYSE
    'CSCO': 'CSCO',   # Cisco Systems, Inc. - NASDAQ
    'CVS': 'CVS',     # CVS Health Corporation - NYSE
    'CVX': 'CVX',     # Chevron Corporation - NYSE
    'DAL': 'DAL',     # Delta Air Lines, Inc. - NYSE
    'DIS': 'DIS',     # The Walt Disney Company - NYSE
    'DOCU': 'DOCU',   # DocuSign, Inc. - NASDAQ
    'EDN': 'EDN',     # Empresa Distribuidora y Comercializadora Norte S.A. - NYSE
    'ELET': 'ELET',   # Centrais Elétricas Brasileiras S.A. - NYSE
    'FDX': 'FDX',     # FedEx Corporation - NYSE
    'GILD': 'GILD',   # Gilead Sciences, Inc. - NASDAQ
    'GLNT': 'GLNT',   # Globant S.A. - NYSE
    'GOLD': 'GOLD',   # Barrick Gold Corporation - NYSE
    'GS': 'GS',       # The Goldman Sachs Group, Inc. - NYSE
    'GSK': 'GSK',     # GlaxoSmithKline plc - NYSE
    'HD': 'HD',       # The Home Depot, Inc. - NYSE
    'HMC': 'HMC',     # Honda Motor Co., Ltd. - NYSE
    'HON': 'HON',     # Honeywell International Inc. - NASDAQ
    'HSBC': 'HSBC',   # HSBC Holdings plc - NYSE
    'IBM': 'IBM',     # International Business Machines Corporation - NYSE
    'INTC': 'INTC',   # Intel Corporation - NASDAQ
    'JNJ': 'JNJ',     # Johnson & Johnson - NYSE
    'JPM': 'JPM',     # JPMorgan Chase & Co. - NYSE
    'KO': 'KO',       # The Coca-Cola Company - NYSE
    'LLY': 'LLY',     # Eli Lilly and Company - NYSE
    'LMT': 'LMT',     # Lockheed Martin Corporation - NYSE
    'MCD': 'MCD',     # McDonald's Corporation - NYSE
    'MELI': 'MELI',   # MercadoLibre, Inc. - NASDAQ
    'MMM': 'MMM',     # 3M Company - NYSE
    'MO': 'MO',       # Altria Group, Inc. - NYSE
    'MRK': 'MRK',     # Merck & Co., Inc. - NYSE
    'MSFT': 'MSFT',   # Microsoft Corporation - NASDAQ
    'MU': 'MU',       # Micron Technology, Inc. - NASDAQ
    'NFLX': 'NFLX',   # Netflix, Inc. - NASDAQ
    'NKE': 'NKE',     # NIKE, Inc. - NYSE
    'NVDA': 'NVDA',   # NVIDIA Corporation - NASDAQ
    'ORCL': 'ORCL',   # Oracle Corporation - NYSE
    'PAM': 'PAM',     # Pampa Energía S.A. - NYSE
    'PANW': 'PANW',   # Palo Alto Networks, Inc. - NASDAQ
    'PBR': 'PBR',     # Petróleo Brasileiro S.A. - Petrobras - NYSE
    'PEP': 'PEP',     # PepsiCo, Inc. - NASDAQ
    'PFE': 'PFE',     # Pfizer Inc. - NYSE
    'PG': 'PG',       # The Procter & Gamble Company - NYSE
    'PLTR': 'PLTR',   # Palantir Technologies Inc. - NYSE
    'PYPL': 'PYPL',   # PayPal Holdings, Inc. - NASDAQ
    'QCOM': 'QCOM',   # QUALCOMM Incorporated - NASDAQ
    'RIO': 'RIO',     # Rio Tinto Group - NYSE
    'ROKU': 'ROKU',   # Roku, Inc. - NASDAQ
    'SBUX': 'SBUX',   # Starbucks Corporation - NASDAQ
    'SNE': 'SNE',     # Sony Group Corporation - NYSE
    'SNOW': 'SNOW',   # Snowflake Inc. - NYSE
    'SPCE': 'SPCE',   # Virgin Galactic Holdings, Inc. - NYSE
    'SPOT': 'SPOT',   # Spotify Technology S.A. - NYSE
    'SQ': 'SQ',       # Block, Inc. (formerly Square, Inc.) - NYSE
    'T': 'T',         # AT&T Inc. - NYSE
    'TSLA': 'TSLA',   # Tesla, Inc. - NASDAQ
    'TXN': 'TXN',     # Texas Instruments Incorporated - NASDAQ
    'UBER': 'UBER',   # Uber Technologies, Inc. - NYSE
    'UNH': 'UNH',     # UnitedHealth Group Incorporated - NYSE
    'V': 'V',         # Visa Inc. - NYSE
    'VALE': 'VALE',   # Vale S.A. - NYSE
    'VIST': 'VIST',   # Vista Oil & Gas, S.A.B. de C.V. - NYSE
    'VZ': 'VZ',       # Verizon Communications Inc. - NYSE
    'WFC': 'WFC',     # Wells Fargo & Company - NYSE
    'WMT': 'WMT',     # Walmart Inc. - NYSE
    'XOM': 'XOM',     # Exxon Mobil Corporation - NYSE
    'ZM': 'ZM',       # Zoom Video Communications, Inc. - NASDAQ
    'NU': 'NU',        # Nu Holdings Ltd. - NYSE
    'NIO': 'NIO',      # NIO Inc. - NYSE
    'JD': 'JD',       # JD.com, Inc. - NYSE
    'PDD': 'PDD',     # Pinduoduo Inc. - NYSE
    'TCEHY': 'TCEHY', # Tencent Holdings Limited - NYSE
    'SPY': 'SPY',     # SPDR S&P 500 ETF Trust - NYSE
    'QQQ': 'QQQ',     # Invesco QQQ Trust - NYSE
    'IWM': 'IWM',     # iShares Russell 2000 ETF - NYSE
    'GLD': 'GLD',     # SPDR Gold Shares - NYSE
    'SLV': 'SLV',     # iShares Silver Trust - NYSE
    'BIL': 'BIL'     # iShares 20+ Year Treasury Bond ETF - NYSE
}

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

def calcular_metricas_cedear(ticker: str) -> Dict:
    data = yf.download(ticker, period="1y", interval="1d")
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

    sma_20 = talib.SMA(close, 20)[-1]
    sma_50 = talib.SMA(close, 50)[-1]
    sma_200 = talib.SMA(close, 200)[-1]
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

def calcular_score_inversion(metricas: Dict) -> Tuple[float, List[str]]:
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

def recomendar_inversiones(capital: float = 10000) -> List[Dict]:
    with Pool(processes=4) as pool:
        metricas_todos = pool.map(calcular_metricas_cedear, CEDEAR_MAPPING.keys())
    metricas_todos = [m for m in metricas_todos if m]

    recomendaciones = []
    for m in metricas_todos:
        score, razones = calcular_score_inversion(m)
        acciones = int(capital / m['precio'])
        inversion_total = acciones * m['precio']
        # Estimación probabilística basada en ATR y score
        prob_suba = min(max((score - 50) / 50, 0), 1)
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

    recomendaciones.sort(key=lambda x: x['score'], reverse=True)
    return recomendaciones[:100]

def generar_reporte_inversiones(capital: float = 10000):
    recomendaciones = recomendar_inversiones(capital)
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
