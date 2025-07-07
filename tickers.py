import requests
from bs4 import BeautifulSoup

def obtener_cedears_top_volumen():
    url = "https://www.invertironline.com/posts/mc-18102024"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, 'html.parser')
    tickers = []
    table = soup.find("table", {"class": "table className"})
    if table:
        for row in table.find_all("tr"):
            cols = row.find_all("td")
            if cols:
                ticker = cols[0].get_text().strip()
                tickers.append(ticker)
    return tickers

def cargar_tickers_usuario(lista_usuario=None):
    lista_usuario = [
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
    "MELI","SNOW"    # Mercado Libre
    ]
    

    if lista_usuario:
        return lista_usuario
    else:
        return obtener_cedears_top_volumen()
    
print(cargar_tickers_usuario())