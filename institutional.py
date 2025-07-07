import requests

def obtener_score_institucional(ticker):
    url = f"https://api.sec.gov/edgar/1.0/search?query={ticker}"
    res = requests.get(url)
    score = 0
    try:
        data = res.json()
        for filing in data.get('filings', []):
            net_purchase = filing.get('netPurchase', 0)
            if net_purchase > 0:
                score += 1
    except:
        score = 0
    return score