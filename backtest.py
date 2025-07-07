def backtest(df, senales):
    capital = 1.0
    peak = capital
    drawdown = 0
    for i in range(len(df)-1):
        if senales[i] == "comprar":
            entry_price = df['Close'].iloc[i]
            exit_price = df['Close'].iloc[i+1]
            capital *= (exit_price / entry_price)
            peak = max(peak, capital)
            dd = (capital - peak) / peak
            drawdown = min(drawdown, dd)
    retorno_acum = (capital - 1) * 100
    return {'retorno_acum': retorno_acum, 'drawdown': drawdown*100}