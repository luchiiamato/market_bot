import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json
from investment_recommendations import calcular_metricas_cedear, calcular_score_inversion

class Backtester:
    def __init__(self, ticker: str, start_date: str, end_date: str, initial_capital: float = 10000):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.data = None
        self.results = None
        
    def load_data(self):
        """Carga datos históricos para el período especificado"""
        try:
            self.data = yf.download(self.ticker, start=self.start_date, end=self.end_date, interval="1d")
            if self.data.empty:
                raise ValueError(f"No se encontraron datos para {self.ticker}")
            return True
        except Exception as e:
            print(f"Error cargando datos para {self.ticker}: {str(e)}")
            return False
            
    def calculate_dynamic_stop_loss(self, row: pd.Series, atr_multiplier: float = 2.0) -> float:
        """Calcula stop loss dinámico basado en ATR"""
        try:
            high = row['High']
            low = row['Low']
            close = row['Close']
            
            # Calcular ATR
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean()
            
            # Calcular stop loss
            stop_loss = close - (atr * atr_multiplier)
            return stop_loss.iloc[-1]
        except Exception as e:
            print(f"Error calculando stop loss: {str(e)}")
            return None
            
    def calculate_position_size(self, capital: float, risk_per_trade: float, 
                              entry_price: float, stop_loss: float) -> int:
        """Calcula el tamaño de la posición basado en el riesgo"""
        try:
            if stop_loss is None or entry_price <= stop_loss:
                return 0
                
            risk_amount = capital * (risk_per_trade / 100)
            risk_per_share = entry_price - stop_loss
            
            if risk_per_share <= 0:
                return 0
                
            position_size = int(risk_amount / risk_per_share)
            return position_size
        except Exception as e:
            print(f"Error calculando tamaño de posición: {str(e)}")
            return 0
            
    def run_backtest(self, risk_per_trade: float = 1.0, atr_multiplier: float = 2.0):
        """Ejecuta el backtest con gestión de riesgo"""
        if not self.load_data():
            return None
            
        results = []
        capital = self.initial_capital
        position = 0
        entry_price = 0
        stop_loss = 0
        
        for i in range(len(self.data)):
            current_date = self.data.index[i]
            current_price = self.data['Close'].iloc[i]
            
            # Calcular métricas para la fecha actual
            historical_data = self.data.iloc[:i+1]
            if len(historical_data) < 200:  # Necesitamos suficientes datos
                continue
                
            # Simular cálculo de métricas
            metrics = calcular_metricas_cedear(self.ticker)
            if not metrics:
                continue
                
            score, razones = calcular_score_inversion(metrics)
            
            # Lógica de trading
            if position == 0 and score >= 70:  # Señal de compra
                stop_loss = self.calculate_dynamic_stop_loss(historical_data, atr_multiplier)
                position = self.calculate_position_size(capital, risk_per_trade, 
                                                     current_price, stop_loss)
                if position > 0:
                    entry_price = current_price
                    capital -= position * current_price
                    
            elif position > 0:
                # Verificar stop loss
                if current_price <= stop_loss:
                    # Cerrar posición
                    capital += position * current_price
                    results.append({
                        'date': current_date,
                        'action': 'SELL',
                        'price': current_price,
                        'position': position,
                        'capital': capital,
                        'reason': 'Stop Loss'
                    })
                    position = 0
                    
                # Verificar take profit (20% desde entrada)
                elif current_price >= entry_price * 1.20:
                    capital += position * current_price
                    results.append({
                        'date': current_date,
                        'action': 'SELL',
                        'price': current_price,
                        'position': position,
                        'capital': capital,
                        'reason': 'Take Profit'
                    })
                    position = 0
                    
                # Verificar señal de venta
                elif score < 50:
                    capital += position * current_price
                    results.append({
                        'date': current_date,
                        'action': 'SELL',
                        'price': current_price,
                        'position': position,
                        'capital': capital,
                        'reason': 'Signal'
                    })
                    position = 0
                    
        # Cerrar posición final si existe
        if position > 0:
            capital += position * self.data['Close'].iloc[-1]
            results.append({
                'date': self.data.index[-1],
                'action': 'SELL',
                'price': self.data['Close'].iloc[-1],
                'position': position,
                'capital': capital,
                'reason': 'End of Period'
            })
            
        self.results = results
        return self.calculate_performance_metrics()
        
    def calculate_performance_metrics(self) -> Dict:
        """Calcula métricas de rendimiento del backtest"""
        if not self.results:
            return None
            
        initial_capital = self.initial_capital
        final_capital = self.results[-1]['capital']
        total_return = ((final_capital - initial_capital) / initial_capital) * 100
        
        # Calcular drawdown máximo
        peak = initial_capital
        max_drawdown = 0
        for result in self.results:
            if result['capital'] > peak:
                peak = result['capital']
            drawdown = (peak - result['capital']) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)
            
        # Calcular ratio de Sharpe (simplificado)
        returns = []
        for i in range(1, len(self.results)):
            daily_return = (self.results[i]['capital'] - self.results[i-1]['capital']) / self.results[i-1]['capital']
            returns.append(daily_return)
            
        if returns:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) != 0 else 0
        else:
            sharpe_ratio = 0
            
        return {
            'initial_capital': initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len([r for r in self.results if r['action'] == 'SELL']),
            'winning_trades': len([r for r in self.results if r['action'] == 'SELL' and r['price'] > entry_price])
        }
        
    def save_results(self, filename: str):
        """Guarda los resultados del backtest en un archivo JSON"""
        if not self.results:
            return
            
        output = {
            'ticker': self.ticker,
            'period': {
                'start': self.start_date,
                'end': self.end_date
            },
            'performance_metrics': self.calculate_performance_metrics(),
            'trades': self.results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
            
def run_backtest_for_ticker(ticker: str, start_date: str, end_date: str, 
                          initial_capital: float = 10000, risk_per_trade: float = 1.0,
                          atr_multiplier: float = 2.0) -> Dict:
    """Función helper para ejecutar backtest para un ticker específico"""
    backtester = Backtester(ticker, start_date, end_date, initial_capital)
    results = backtester.run_backtest(risk_per_trade, atr_multiplier)
    
    if results:
        filename = f"backtest_results_{ticker}_{start_date}_{end_date}.json"
        backtester.save_results(filename)
        print(f"Backtest completado para {ticker}. Resultados guardados en {filename}")
        return results
    else:
        print(f"Error ejecutando backtest para {ticker}")
        return None

if __name__ == "__main__":
    # Ejemplo de uso
    ticker = "AAPL"
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    
    results = run_backtest_for_ticker(ticker, start_date, end_date)
    if results:
        print("\nResultados del Backtest:")
        print(f"Retorno Total: {results['total_return']:.2f}%")
        print(f"Drawdown Máximo: {results['max_drawdown']:.2f}%")
        print(f"Ratio de Sharpe: {results['sharpe_ratio']:.2f}")
        print(f"Total de Operaciones: {results['total_trades']}")
        print(f"Operaciones Ganadoras: {results['winning_trades']}") 