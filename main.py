import yfinance as yf
import pandas as pd
from technical import calcular_indicadores, generar_senal_tecnica
from ml_prediction import predecir_direccion
from news_sentiment import analizar_sentimiento_noticias
from output import generar_reporte

def ejecutar_pipeline(tickers: list) -> pd.DataFrame:
    """
    Ejecuta el pipeline completo de análisis para una lista de tickers
    """
    resultados = []
    
    for ticker in tickers:
        try:
            print(f"\nProcesando {ticker}...")
            
            # Obtener datos con auto_adjust=True explícitamente
            data = yf.download(ticker, period="1y", interval="1d", auto_adjust=True)
            if data.empty:
                print(f"❌ No se pudieron obtener datos para {ticker}")
                continue
                
            # Validar que tenemos todas las columnas necesarias
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in data.columns for col in required_columns):
                print(f"❌ Datos incompletos para {ticker}. Columnas faltantes: {[col for col in required_columns if col not in data.columns]}")
                continue
            
            # Calcular indicadores técnicos
            data = calcular_indicadores(data)
            if data is None:
                print(f"❌ Error calculando indicadores para {ticker}")
                continue
            
            # Generar señal técnica
            senal_tecnica = generar_senal_tecnica(data)
            if senal_tecnica is None:
                print(f"❌ Error generando señal técnica para {ticker}")
                continue
            
            # Generar predicción ML
            prediccion, confianza = predecir_direccion(data)
            if prediccion == "error":
                print(f"❌ Error en predicción para {ticker}")
                continue
            
            # Analizar sentimiento
            sentimiento = analizar_sentimiento_noticias(ticker)
            
            # Almacenar resultados
            resultados.append({
                "ticker": ticker,
                "precio": data["Close"].iloc[-1].item(),
                "senal": senal_tecnica["senal"],
                "razones": senal_tecnica["razones"],
                "prediccion": prediccion,
                "confianza": confianza,
                "stop_loss": senal_tecnica["stop_loss"],
                "take_profit": senal_tecnica["take_profit"],
                "sentimiento": sentimiento
            })
            
            print(f"✅ {ticker} procesado exitosamente.")
            
        except Exception as e:
            print(f"❌ Error procesando {ticker}: {str(e)}")
            continue
    
    # Generar reporte
    if resultados:
        df_resultados = pd.DataFrame(resultados)
        generar_reporte(df_resultados)
        return df_resultados
    else:
        print("❌ No se pudo generar ningún resultado")
        return None

if __name__ == "__main__":
    # Lista de tickers a analizar
    tickers = [
    "AAPL",   # Apple Inc.
    "PLTR",   # Palantir Technologies
    "QQQ",    # Invesco QQQ Trust
    "SPY",    # SPDR S&P 500 ETF
    "TSLA",   # Tesla Inc.
    "NVDA",   # NVIDIA Corporation
    "NU",     # Nu Holdings
    "NIO",    # Nio Inc.
    "BABA",   # Alibaba Group
    "TSM",    # Taiwan Semiconductor
    "AMZN",   # Amazon.com Inc.
    "GOOGL",  # Alphabet Inc.
    "JPM",    # JPMorgan Chase
    "COIN",   # Coinbase Global
    "META",   # Meta Platforms
    "MELI","SNOW"  ,'NVTS'  # Mercado Libre
    ]
    
    # Ejecutar pipeline
    resultados = ejecutar_pipeline(tickers)