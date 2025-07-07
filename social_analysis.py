import snscrape.modules.twitter as sntwitter
from datetime import datetime, timedelta
from news_sentiment import analizar_sentimiento_noticias

def obtener_menciones_tweets(ticker, dias=7, max_tweets=100):
    since = (datetime.now() - timedelta(days=dias)).strftime('%Y-%m-%d')
    query = f"{ticker} since:{since}"
    tweets = []
    for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
        if i >= max_tweets:
            break
        tweets.append(tweet.content)
    return tweets

def analizar_redes_sociales(ticker):
    textos = obtener_menciones_tweets(ticker)
    sentimiento = analizar_sentimiento_noticias(textos)
    volumen = len(textos)
    return {'volumen': volumen, 'sentimiento': sentimiento}