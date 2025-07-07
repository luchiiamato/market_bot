import yfinance as yf
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import json
import talib

# Lista de CEDEARs disponibles con sus tickers en NYSE
CEDEAR_MAPPING = {
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

def calcular_metricas_cedear(ticker: str) -> Dict:
    """
    Calcula métricas técnicas avanzadas para un CEDEAR
    """
    try:
        print(f"\nProcesando {ticker}...")
        
        # Obtener datos históricos
        data = yf.download(ticker, period="1y", interval="1d")
        if data.empty or len(data) < 200:  # Necesitamos al menos 200 días para SMA-200
            print(f"Error: Datos insuficientes para {ticker}")
            return None

        print(f"Obtenidos {len(data)} días de datos para {ticker}")

        # Validar que tenemos todas las columnas necesarias
        required_columns = ['Close', 'High', 'Low', 'Volume']
        if not all(col in data.columns for col in required_columns):
            print(f"Error: Faltan columnas necesarias para {ticker}")
            return None

        # Limpiar datos y convertir a float
        try:
            data = data.astype(float)
            print("Datos convertidos a float exitosamente")
        except Exception as e:
            print(f"Error convirtiendo datos a float: {str(e)}")
            return None
        
        # Eliminar filas con NaN
        data = data.dropna()
        
        if len(data) < 200:
            print(f"Error: Insuficientes datos después de limpiar NaN para {ticker}")
            return None

        # Datos básicos con validación
        try:
            # Obtener los últimos dos precios de cierre
            ultimos_precios = data['Close'].iloc[-2:].values
            if len(ultimos_precios) < 2:
                raise ValueError("No hay suficientes datos de precios")
            
            # Convertir arrays numpy a valores escalares
            precio_actual = float(ultimos_precios[-1])
            precio_anterior = float(ultimos_precios[-2])
            print('precio actual')
            print(precio_actual)
            print('precio anterior')
            print(precio_anterior)
            # Verificar que los precios son numéricos y válidos
            if not (isinstance(precio_actual, (int, float)) and isinstance(precio_anterior, (int, float))):
                raise ValueError(f"Precios no son numéricos: actual={type(precio_actual)}, anterior={type(precio_anterior)}")
            
            if np.isnan(precio_actual) or np.isnan(precio_anterior):
                raise ValueError("Precios contienen valores NaN")
            
            if precio_anterior == 0:
                raise ValueError("Precio anterior es cero")
            
            cambio_diario = ((precio_actual - precio_anterior) / precio_anterior) * 100
            
            print(f"Precio actual: {precio_actual:.2f}, Cambio diario: {cambio_diario:.2f}%")
        except Exception as e:
            print(f"Error procesando precios básicos para {ticker}: {str(e)}")
            return None
        
        # Medias móviles con validación
        try:
            # Obtener las medias móviles
            sma_20_raw = data['Close'].rolling(window=20).mean().iloc[-1:].values[0]
            sma_50_raw = data['Close'].rolling(window=50).mean().iloc[-1:].values[0]
            sma_200_raw = data['Close'].rolling(window=200).mean().iloc[-1:].values[0]
            ema_12_raw = data['Close'].ewm(span=12, adjust=False).mean().iloc[-1:].values[0]
            ema_26_raw = data['Close'].ewm(span=26, adjust=False).mean().iloc[-1:].values[0]
            
            # Convertir a float y verificar
            sma_20 = float(sma_20_raw)
            sma_50 = float(sma_50_raw)
            sma_200 = float(sma_200_raw)
            ema_12 = float(ema_12_raw)
            ema_26 = float(ema_26_raw)
            
            print("Valores de medias móviles:")
            print(f"SMA20: {sma_20}")
            print(f"SMA50: {sma_50}")
            print(f"SMA200: {sma_200}")
            print(f"EMA12: {ema_12}")
            print(f"EMA26: {ema_26}")
            
            # Verificar que las medias móviles son numéricas y válidas
            if any(np.isnan([sma_20, sma_50, sma_200, ema_12, ema_26])):
                raise ValueError("Algunas medias móviles son NaN")
            
            print(f"Medias móviles calculadas - SMA20: {sma_20:.2f}, SMA50: {sma_50:.2f}, SMA200: {sma_200:.2f}")
        except Exception as e:
            print(f"Error calculando medias móviles para {ticker}: {str(e)}")
            return None

        # Preparar arrays para TA-Lib
        print("Preparando arrays para indicadores técnicos...")
        try:
            # Convertir a numpy arrays y asegurar que son 1D
            close_prices = np.array(data['Close'].values, dtype=float)
            high_prices = np.array(data['High'].values, dtype=float)
            low_prices = np.array(data['Low'].values, dtype=float)
            volume = np.array(data['Volume'].values, dtype=float)
            
            # Verificar dimensiones
            print(f"Dimensiones - Close: {close_prices.shape}, High: {high_prices.shape}, Low: {low_prices.shape}")
            
            # Verificar que los arrays tienen la longitud correcta y son numéricos
            if len(close_prices) < 200:
                raise ValueError("Insuficientes datos para indicadores técnicos")
            
            if any(np.isnan(close_prices)) or any(np.isnan(high_prices)) or any(np.isnan(low_prices)):
                raise ValueError("Arrays contienen valores NaN")
                
        except Exception as e:
            print(f"Error preparando arrays para {ticker}: {str(e)}")
            return None

        # RSI con validación
        try:
            print("Calculando RSI...")
            close_prices = data['Close'].dropna().astype(float).to_numpy().flatten()
            
            if len(close_prices) < 15:
                raise ValueError("No hay suficientes datos para calcular RSI (min: 15)")

            rsi_series = talib.RSI(close_prices, timeperiod=14)

            # Filtrar NaN
            rsi_series = rsi_series[~np.isnan(rsi_series)]

            if len(rsi_series) == 0:
                raise ValueError("RSI vacío tras filtrado")

            rsi_value = float(rsi_series[-1])
            print(f"RSI calculado: {rsi_value:.2f}")

        except Exception as e:
            print(f"Error calculando RSI para {ticker}: {str(e)}")
            rsi_value = 50  # Valor neutral si falla el cálculo
        
        # MACD con validación
        try:
            print("Calculando MACD...")
            close_prices = data['Close'].dropna().astype(float).to_numpy().flatten()

            if len(close_prices) < 26:
                raise ValueError("No hay suficientes datos para calcular MACD (mínimo 26)")

            macd, signal, hist = talib.MACD(close_prices, fastperiod=12, slowperiod=26, signalperiod=9)

            # Filtrar NaN de los arrays resultantes
            macd_clean = macd[~np.isnan(macd)]
            signal_clean = signal[~np.isnan(signal)]
            hist_clean = hist[~np.isnan(hist)]

            if len(macd_clean) == 0 or len(signal_clean) == 0 or len(hist_clean) == 0:
                raise ValueError("MACD, señal o histograma vacíos tras filtrado")

            macd_value = float(macd_clean[-1])
            signal_value = float(signal_clean[-1])
            hist_value = float(hist_clean[-1])

            print(f"MACD calculado - Valor: {macd_value:.4f}, Señal: {signal_value:.4f}, Histograma: {hist_value:.4f}")

        except Exception as e:
            print(f"Error calculando MACD para {ticker}: {str(e)}")
            macd_value = 0
            signal_value = 0
            hist_value = 0
        
        
        # Bandas de Bollinger con validación
        try:
            print("Calculando Bandas de Bollinger...")
            close_prices = data['Close'].dropna().astype(float).to_numpy().flatten()

            if len(close_prices) < 20:
                raise ValueError("No hay suficientes datos para calcular Bandas de Bollinger (mínimo 20)")

            upper, middle, lower = talib.BBANDS(close_prices, timeperiod=20, nbdevup=2, nbdevdn=2)

            # Filtrar NaN de los arrays resultantes
            upper_clean = upper[~np.isnan(upper)]
            middle_clean = middle[~np.isnan(middle)]
            lower_clean = lower[~np.isnan(lower)]

            if len(upper_clean) == 0 or len(middle_clean) == 0 or len(lower_clean) == 0:
                raise ValueError("Bandas de Bollinger vacías tras filtrado")

            bb_upper = float(upper_clean[-1])
            bb_middle = float(middle_clean[-1])
            bb_lower = float(lower_clean[-1])

            print(f"Bandas de Bollinger calculadas - Superior: {bb_upper:.2f}, Media: {bb_middle:.2f}, Inferior: {bb_lower:.2f}")

        except Exception as e:
            print(f"Error calculando Bollinger Bands para {ticker}: {str(e)}")
            bb_upper = precio_actual * 1.02
            bb_middle = precio_actual
            bb_lower = precio_actual * 0.98
        
        # Volumen con validación
        try:
            # Obtener valores raw
            volumen_promedio_raw = data['Volume'].rolling(window=20).mean().iloc[-1:].values[0]
            volumen_actual_raw = volume[-1]
            
            # Convertir a float
            volumen_promedio = float(volumen_promedio_raw)
            volumen_actual = float(volumen_actual_raw)
            
            print(f"Volumen raw - Actual: {volumen_actual_raw}, Promedio: {volumen_promedio_raw}")
            
            if np.isnan(volumen_promedio) or np.isnan(volumen_actual):
                raise ValueError("Valores de volumen contienen NaN")
            
            if volumen_promedio <= 0:
                raise ValueError("Volumen promedio es cero o negativo")
                
            ratio_volumen = volumen_actual / volumen_promedio
            print(f"Volumen procesado - Actual: {volumen_actual}, Promedio: {volumen_promedio}, Ratio: {ratio_volumen}")
        except Exception as e:
            print(f"Error procesando volumen para {ticker}: {str(e)}")
            return None
        
        # ATR con validación
        try:
            print("Calculando ATR...")
            # Asegurar arrays limpios y floats
            high_clean = data['High'].dropna().astype(float).to_numpy().flatten()
            low_clean = data['Low'].dropna().astype(float).to_numpy().flatten()
            close_clean = data['Close'].dropna().astype(float).to_numpy().flatten()

            # Igualar largo mínimo
            min_len = min(len(high_clean), len(low_clean), len(close_clean))
            high_clean = high_clean[-min_len:]
            low_clean = low_clean[-min_len:]
            close_clean = close_clean[-min_len:]

            if min_len < 14:
                raise ValueError("No hay suficientes datos para calcular ATR (mínimo 14)")

            atr = talib.ATR(high_clean, low_clean, close_clean, timeperiod=14)

            atr_clean = atr[~np.isnan(atr)]
            if len(atr_clean) == 0:
                raise ValueError("ATR vacío tras filtrado")

            atr_value = float(atr_clean[-1])
            print(f"ATR calculado: {atr_value:.2f}")

        except Exception as e:
            print(f"Error calculando ATR para {ticker}: {str(e)}")
            atr_value = abs(precio_actual - precio_anterior)

        # Stochastic con validación
        try:
            print("Calculando Stochastic...")
            high_clean = data['High'].dropna().astype(float).to_numpy().flatten()
            low_clean = data['Low'].dropna().astype(float).to_numpy().flatten()
            close_clean = data['Close'].dropna().astype(float).to_numpy().flatten()

            min_len = min(len(high_clean), len(low_clean), len(close_clean))
            high_clean = high_clean[-min_len:]
            low_clean = low_clean[-min_len:]
            close_clean = close_clean[-min_len:]

            if min_len < 14:
                raise ValueError("No hay suficientes datos para calcular Stochastic (mínimo 14)")

            slowk, slowd = talib.STOCH(high_clean, low_clean, close_clean,
                                    fastk_period=14, slowk_period=3,
                                    slowk_matype=0, slowd_period=3, slowd_matype=0)

            slowk_clean = slowk[~np.isnan(slowk)]
            slowd_clean = slowd[~np.isnan(slowd)]

            if len(slowk_clean) == 0 or len(slowd_clean) == 0:
                raise ValueError("Stochastic vacío tras filtrado")

            stoch_k = float(slowk_clean[-1])
            stoch_d = float(slowd_clean[-1])
            print(f"Stochastic calculado - K: {stoch_k:.2f}, D: {stoch_d:.2f}")

        except Exception as e:
            print(f"Error calculando Stochastic para {ticker}: {str(e)}")
            stoch_k = 50
            stoch_d = 50

        # Momentum con validación
        try:
            print("Calculando Momentum...")
            close_clean = data['Close'].dropna().astype(float).to_numpy().flatten()

            if len(close_clean) < 10:
                raise ValueError("No hay suficientes datos para calcular Momentum (mínimo 10)")

            momentum = talib.MOM(close_clean, timeperiod=10)

            momentum_clean = momentum[~np.isnan(momentum)]
            if len(momentum_clean) == 0:
                raise ValueError("Momentum vacío tras filtrado")

            momentum_value = float(momentum_clean[-1])
            print(f"Momentum calculado: {momentum_value:.2f}")

        except Exception as e:
            print(f"Error calculando Momentum para {ticker}: {str(e)}")
            momentum_value = precio_actual - precio_anterior
        
        # Análisis de tendencia
        tendencia_corta = "ALCISTA" if precio_actual > sma_20 else "BAJISTA"
        tendencia_media = "ALCISTA" if precio_actual > sma_50 else "BAJISTA"
        tendencia_larga = "ALCISTA" if precio_actual > sma_200 else "BAJISTA"
        
        print(f"Tendencias - Corta: {tendencia_corta}, Media: {tendencia_media}, Larga: {tendencia_larga}")
        
        # Fuerza de la tendencia
        fuerza_tendencia = 0
        if tendencia_corta == "ALCISTA": fuerza_tendencia += 1
        if tendencia_media == "ALCISTA": fuerza_tendencia += 1
        if tendencia_larga == "ALCISTA": fuerza_tendencia += 1
        
        print(f"Fuerza de tendencia: {fuerza_tendencia}/3")
        
        # Validación final de todos los valores antes de retornar
        try:
            resultado = {
                'ticker': ticker,
                'precio': precio_actual,
                'cambio_diario': cambio_diario,
                'sma_20': sma_20,
                'sma_50': sma_50,
                'sma_200': sma_200,
                'ema_12': ema_12,
                'ema_26': ema_26,
                'rsi': rsi_value,
                'macd': macd_value,
                'macd_signal': signal_value,
                'macd_hist': hist_value,
                'bb_upper': bb_upper,
                'bb_middle': bb_middle,
                'bb_lower': bb_lower,
                'ratio_volumen': ratio_volumen,
                'atr': atr_value,
                'stoch_k': stoch_k,
                'stoch_d': stoch_d, 
                'momentum': momentum_value,
                'tendencia_corta': tendencia_corta,
                'tendencia_media': tendencia_media,
                'tendencia_larga': tendencia_larga,
                'fuerza_tendencia': fuerza_tendencia,
                'score': 0  # Se calculará después
            }
            
            # Validar que todos los valores numéricos son válidos
            for key, value in resultado.items():
                if isinstance(value, (int, float)) and (np.isnan(value) or np.isinf(value)):
                    raise ValueError(f"Valor inválido encontrado en {key}")
            
            return resultado
            
        except Exception as e:
            print(f"Error en la validación final de datos para {ticker}: {str(e)}")
            return None
            
    except Exception as e:
        print(f"Error general calculando métricas para {ticker}: {str(e)}")
        return None

def calcular_score_inversion(metricas: Dict) -> Tuple[float, List[str]]:
    """
    Calcula un score de inversión basado en múltiples factores y retorna las razones
    """
    score = 0
    razones = []
    
    # Factor 1: Fuerza de la Tendencia (30%)
    fuerza_tendencia = metricas['fuerza_tendencia']
    score += fuerza_tendencia * 10
    razones.append(f"Fuerza de tendencia: {fuerza_tendencia}/3 timeframes alcistas")
    
    # Factor 2: RSI (10%)
    rsi = metricas['rsi']
    if 30 <= rsi <= 70:
        score += 10
        razones.append(f"RSI en zona neutral ({rsi:.1f})")
    elif rsi < 30:
        score += 15
        razones.append(f"RSI en sobreventa ({rsi:.1f}), posible rebote")
    elif rsi > 70:
        score += 5
        razones.append(f"RSI en sobrecompra ({rsi:.1f}), precaución")
    
    # Factor 3: MACD (15%)
    if metricas['macd'] > metricas['macd_signal']:
        score += 15
        razones.append("MACD por encima de la señal, momentum alcista")
    else:
        score += 5
        razones.append("MACD por debajo de la señal, momentum bajista")
    
    # Factor 4: Bandas de Bollinger (10%)
    precio = metricas['precio']
    if precio < metricas['bb_lower']:
        score += 15
        razones.append("Precio por debajo de la banda inferior de Bollinger, posible rebote")
    elif precio > metricas['bb_upper']:
        score += 5
        razones.append("Precio por encima de la banda superior de Bollinger, posible corrección")
    else:
        score += 10
        razones.append("Precio dentro de las bandas de Bollinger")
    
    # Factor 5: Volumen (10%)
    ratio_volumen = metricas['ratio_volumen']
    if ratio_volumen > 1.5:
        score += 15
        razones.append(f"Volumen fuerte ({ratio_volumen:.1f}x promedio)")
    elif ratio_volumen > 1.2:
        score += 10
        razones.append(f"Volumen moderado ({ratio_volumen:.1f}x promedio)")
    else:
        score += 5
        razones.append(f"Volumen débil ({ratio_volumen:.1f}x promedio)")
    
    # Factor 6: Stochastic (10%)
    if metricas['stoch_k'] < 20 and metricas['stoch_d'] < 20:
        score += 15
        razones.append("Stochastic en sobreventa, posible rebote")
    elif metricas['stoch_k'] > 80 and metricas['stoch_d'] > 80:
        score += 5
        razones.append("Stochastic en sobrecompra, posible corrección")
    else:
        score += 10
        razones.append("Stochastic en zona neutral")
    
    # Factor 7: Momentum (15%)
    if metricas['momentum'] > 0:
        score += 15
        razones.append("Momentum positivo")
    else:
        score += 5
        razones.append("Momentum negativo")
    
    # Ajustes adicionales
    if metricas['tendencia_corta'] == "ALCISTA" and metricas['tendencia_media'] == "ALCISTA":
        score += 10
        razones.append("Tendencia alcista confirmada en corto y medio plazo")
    
    if metricas['tendencia_larga'] == "ALCISTA":
        score += 5
        razones.append("Tendencia alcista en largo plazo")
    
    return score, razones

def recomendar_inversiones(capital: float = 10000) -> List[Dict]:
    """
    Recomienda las mejores inversiones en CEDEARs basado en el capital disponible
    """
    print("Analizando oportunidades de inversión en CEDEARs...")
    
    # Calcular métricas para todos los CEDEARs
    metricas_todos = []
    for ticker in CEDEAR_MAPPING.keys():
        metricas = calcular_metricas_cedear(ticker)
        if metricas:
            score, razones = calcular_score_inversion(metricas)
            metricas['score'] = score
            metricas['razones'] = razones
            metricas_todos.append(metricas)
    
    # Ordenar por score
    metricas_todos.sort(key=lambda x: x['score'], reverse=True)
    
    # Seleccionar top 10
    top_10 = metricas_todos[:200]
    
    # Calcular recomendaciones
    recomendaciones = []
    for metrica in top_10:
        # Calcular cantidad de acciones que se pueden comprar
        acciones_posibles = int(capital / metrica['precio'])
        inversion_total = acciones_posibles * metrica['precio']
        
        # Calcular potencial de ganancia basado en múltiples factores
        if metrica['fuerza_tendencia'] == 3 and metrica['rsi'] < 70:
            potencial_ganancia = inversion_total * 0.20  # 20% objetivo
        elif metrica['fuerza_tendencia'] >= 2:
            potencial_ganancia = inversion_total * 0.15  # 15% objetivo
        else:
            potencial_ganancia = inversion_total * 0.10  # 10% objetivo
        
        recomendaciones.append({
            'ticker': metrica['ticker'],
            'precio_actual': round(metrica['precio'], 2),
            'score': round(metrica['score'], 2),
            'tendencia_corta': metrica['tendencia_corta'],
            'tendencia_media': metrica['tendencia_media'],
            'tendencia_larga': metrica['tendencia_larga'],
            'rsi': round(metrica['rsi'], 2),
            'acciones_recomendadas': acciones_posibles,
            'inversion_total': round(inversion_total, 2),
            'potencial_ganancia': round(potencial_ganancia, 2),
            'razones': metrica['razones']
        })
    
    return recomendaciones

def generar_reporte_inversiones(capital: float = 10000):
    """
    Genera un archivo JSON con recomendaciones detalladas de inversión
    """
    recomendaciones = recomendar_inversiones(capital)
    
    # Preparar el reporte en formato JSON
    reporte = {
        "fecha_generacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "capital_disponible": capital,
        "recomendaciones": []
    }
    
    for i, rec in enumerate(recomendaciones, 1):
        recomendacion = {
            "orden_recomendado": i,
            "ticker": rec['ticker'],
            "score": rec['score'],
            "precio_actual": rec['precio_actual'],
            "tendencias": {
                "corta": rec['tendencia_corta'],
                "media": rec['tendencia_media'],
                "larga": rec['tendencia_larga']
            },
            "rsi": rec['rsi'],
            "acciones_recomendadas": rec['acciones_recomendadas'],
            "inversion_total": rec['inversion_total'],
            "potencial_ganancia": rec['potencial_ganancia'],
            "razones": rec['razones'],
            "riesgo": "BAJO" if rec['score'] >= 80 else "MEDIO" if rec['score'] >= 60 else "ALTO",
            "tiempo_recomendado_hold": "LARGO" if rec['tendencia_larga'] == "ALCISTA" and rec['rsi'] < 70 else "MEDIO" if rec['tendencia_media'] == "ALCISTA" else "CORTO"
        }
        reporte["recomendaciones"].append(recomendacion)
    
    # Guardar el reporte en un archivo JSON
    nombre_archivo = f"recomendaciones_inversion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(f'recomendaciones/{nombre_archivo}', 'w', encoding='utf-8') as f:
        json.dump(reporte, f, indent=4, ensure_ascii=False)
    
    print(f"\nReporte generado exitosamente: {nombre_archivo}")
    print("⚠️ ADVERTENCIA: Este análisis es solo informativo y no constituye asesoramiento financiero.")
    print("   Considere su tolerancia al riesgo y realice su propio análisis antes de invertir.")

if __name__ == "__main__":
    generar_reporte_inversiones() 