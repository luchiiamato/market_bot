import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

class QualityFilters:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.data = None
        
    def load_data(self, period: str = "1y", interval: str = "1d") -> bool:
        """Carga datos históricos del ticker"""
        try:
            self.data = yf.download(self.ticker, period=period, interval=interval)
            if self.data.empty:
                raise ValueError(f"No se encontraron datos para {self.ticker}")
            return True
        except Exception as e:
            print(f"Error cargando datos para {self.ticker}: {str(e)}")
            return False
            
    def check_liquidity(self, min_avg_volume: float = 100000) -> Tuple[bool, float]:
        """
        Verifica la liquidez del activo
        Retorna: (cumple_criterio, volumen_promedio)
        """
        try:
            if self.data is None:
                if not self.load_data():
                    return False, 0
                    
            avg_volume = float(self.data['Volume'].mean().iloc[0])
            return avg_volume >= min_avg_volume, avg_volume
            
        except Exception as e:
            print(f"Error verificando liquidez para {self.ticker}: {str(e)}")
            return False, 0
            
    def check_volatility(self, max_volatility: float = 0.05) -> Tuple[bool, float]:
        """
        Verifica la volatilidad del activo
        Retorna: (cumple_criterio, volatilidad)
        """
        try:
            if self.data is None:
                if not self.load_data():
                    return False, 0
                    
            # Calcular retornos diarios
            returns = self.data['Close'].pct_change().dropna()
            
            # Calcular volatilidad anualizada
            volatility = float(returns.std().iloc[0] * np.sqrt(252))
            
            return volatility <= max_volatility, volatility
            
        except Exception as e:
            print(f"Error verificando volatilidad para {self.ticker}: {str(e)}")
            return False, 0
            
    def check_trend_strength(self, min_strength: float = 0.6) -> Tuple[bool, float]:
        """
        Verifica la fuerza de la tendencia usando ADX
        Retorna: (cumple_criterio, fuerza_tendencia)
        """
        try:
            if self.data is None:
                if not self.load_data():
                    return False, 0
                    
            # Calcular ADX
            high = self.data['High'].values.flatten()
            low = self.data['Low'].values.flatten()
            close = self.data['Close'].values.flatten()
            
            # Calcular True Range
            tr1 = high - low
            tr2 = np.abs(high - np.roll(close, 1))
            tr3 = np.abs(low - np.roll(close, 1))
            tr = np.maximum(np.maximum(tr1, tr2), tr3)
            
            # Calcular +DM y -DM
            up_move = high - np.roll(high, 1)
            down_move = np.roll(low, 1) - low
            
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
            
            # Calcular +DI y -DI
            tr14 = pd.Series(tr).rolling(window=14).sum().values
            plus_di14 = 100 * pd.Series(plus_dm).rolling(window=14).sum().values / tr14
            minus_di14 = 100 * pd.Series(minus_dm).rolling(window=14).sum().values / tr14
            
            # Calcular ADX
            dx = 100 * np.abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14)
            adx = pd.Series(dx).rolling(window=14).mean()
            
            # Obtener último valor de ADX
            trend_strength = float(adx.iloc[-1])
            
            return trend_strength >= min_strength, trend_strength
            
        except Exception as e:
            print(f"Error verificando fuerza de tendencia para {self.ticker}: {str(e)}")
            return False, 0
            
    def check_price_range(self, min_price: float = 5.0, max_price: float = 1000.0) -> Tuple[bool, float]:
        """
        Verifica que el precio esté dentro de un rango aceptable
        Retorna: (cumple_criterio, precio_actual)
        """
        try:
            if self.data is None:
                if not self.load_data():
                    return False, 0
                    
            current_price = float(self.data['Close'].iloc[-1].iloc[0])
            return min_price <= current_price <= max_price, current_price
            
        except Exception as e:
            print(f"Error verificando rango de precio para {self.ticker}: {str(e)}")
            return False, 0
            
    def check_market_cap(self, min_market_cap: float = 1e9) -> Tuple[bool, float]:
        """
        Verifica la capitalización de mercado
        Retorna: (cumple_criterio, market_cap)
        """
        try:
            ticker_info = yf.Ticker(self.ticker)
            market_cap = float(ticker_info.info.get('marketCap', 0))
            
            return market_cap >= min_market_cap, market_cap
            
        except Exception as e:
            print(f"Error verificando capitalización de mercado para {self.ticker}: {str(e)}")
            return False, 0
            
    def check_all_filters(self, filter_params: Dict = None) -> Dict:
        """
        Verifica todos los filtros de calidad
        Retorna diccionario con resultados de cada filtro
        """
        if filter_params is None:
            filter_params = {
                'min_avg_volume': 100000,
                'max_volatility': 0.05,
                'min_trend_strength': 0.6,
                'min_price': 5.0,
                'max_price': 1000.0,
                'min_market_cap': 1e9
            }
            
        results = {}
        
        # Verificar liquidez
        liquidity_ok, avg_volume = self.check_liquidity(filter_params['min_avg_volume'])
        results['liquidity'] = {
            'passed': bool(liquidity_ok),
            'value': float(avg_volume),
            'threshold': float(filter_params['min_avg_volume'])
        }
        
        # Verificar volatilidad
        volatility_ok, volatility = self.check_volatility(filter_params['max_volatility'])
        results['volatility'] = {
            'passed': bool(volatility_ok),
            'value': float(volatility),
            'threshold': float(filter_params['max_volatility'])
        }
        
        # Verificar fuerza de tendencia
        trend_ok, trend_strength = self.check_trend_strength(filter_params['min_trend_strength'])
        results['trend_strength'] = {
            'passed': bool(trend_ok),
            'value': float(trend_strength),
            'threshold': float(filter_params['min_trend_strength'])
        }
        
        # Verificar rango de precio
        price_ok, current_price = self.check_price_range(
            filter_params['min_price'],
            filter_params['max_price']
        )
        results['price_range'] = {
            'passed': bool(price_ok),
            'value': float(current_price),
            'threshold': {
                'min': float(filter_params['min_price']),
                'max': float(filter_params['max_price'])
            }
        }
        
        # Verificar capitalización de mercado
        market_cap_ok, market_cap = self.check_market_cap(filter_params['min_market_cap'])
        results['market_cap'] = {
            'passed': bool(market_cap_ok),
            'value': float(market_cap),
            'threshold': float(filter_params['min_market_cap'])
        }
        
        # Calcular score general
        passed_filters = sum(1 for result in results.values() if result['passed'])
        total_filters = len(results)
        results['overall_score'] = float(passed_filters / total_filters)
        
        return results

def check_ticker_quality(ticker: str, filter_params: Dict = None) -> Dict:
    """Función helper para verificar la calidad de un ticker"""
    filters = QualityFilters(ticker)
    results = filters.check_all_filters(filter_params)
    
    print(f"\nResultados de Filtros de Calidad para {ticker}:")
    print(f"Score General: {results['overall_score']*100:.1f}%")
    
    for filter_name, filter_result in results.items():
        if filter_name != 'overall_score':
            print(f"\n{filter_name.upper()}:")
            print(f"Pasó: {'Sí' if filter_result['passed'] else 'No'}")
            print(f"Valor: {filter_result['value']:.2f}")
            if isinstance(filter_result['threshold'], dict):
                print(f"Umbral: {filter_result['threshold']['min']:.2f} - {filter_result['threshold']['max']:.2f}")
            else:
                print(f"Umbral: {filter_result['threshold']:.2f}")
    
    return results

if __name__ == "__main__":
    # Ejemplo de uso
    ticker = "AAPL"
    results = check_ticker_quality(ticker) 