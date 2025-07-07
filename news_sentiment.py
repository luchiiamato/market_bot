from transformers import pipeline
import yfinance as yf
import pandas as pd

def get_news_sentiment(ticker: str) -> dict:
    """
    Obtiene el sentimiento de las noticias recientes del ticker
    """
    try:
        # Obtener noticias recientes
        stock = yf.Ticker(ticker)
        news = stock.news
        
        if not news:
            return {"positivo": 0, "negativo": 0, "neutral": 0}
            
        # Inicializar pipeline de sentimiento
        sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            revision="714eb0f"
        )
        
        # Analizar títulos de noticias
        titles = [item.get('title', '') for item in news[:5]]  # Últimas 5 noticias
        if not titles:
            return {"positivo": 0, "negativo": 0, "neutral": 0}
            
        # Calcular sentimiento
        resultados = sentiment_pipeline(titles)
        positivo = sum(1 for r in resultados if r["label"] == "POSITIVE")
        negativo = sum(1 for r in resultados if r["label"] == "NEGATIVE")
        neutral = len(resultados) - positivo - negativo
        
        return {
            "positivo": positivo,
            "negativo": negativo,
            "neutral": neutral,
            "total": len(resultados)
        }
        
    except Exception as e:
        print(f"⚠️ Error en análisis de sentimiento para {ticker}: {str(e)}")
        return {"positivo": 0, "negativo": 0, "neutral": 0, "total": 0}

def analizar_sentimiento_noticias(ticker: str) -> float:
    """
    Analiza el sentimiento de las noticias y retorna un score normalizado
    """
    try:
        sentimiento = get_news_sentiment(ticker)
        
        if sentimiento["total"] == 0:
            return 0.0
            
        # Calcular score normalizado (-1 a 1)
        score = (sentimiento["positivo"] - sentimiento["negativo"]) / sentimiento["total"]
        return round(score, 2)
        
    except Exception as e:
        print(f"⚠️ Error calculando score de sentimiento para {ticker}: {str(e)}")
        return 0.0