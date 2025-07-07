import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def descargar_datos_historicos(ticker, años=5):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*años)
    data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'),
                        end=end_date.strftime('%Y-%m-%d'), progress=False)
    print(data)
    if data.empty:
        raise ValueError(f"No se obtuvieron datos para {ticker}")
    data.reset_index(inplace=True)
    return data