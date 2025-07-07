import numpy as np
from typing import Dict, List, Tuple
from backtesting import Backtester
import json
from datetime import datetime, timedelta
import concurrent.futures
from itertools import product

class ParameterOptimizer:
    def __init__(self, ticker: str, start_date: str, end_date: str, initial_capital: float = 10000):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.results = []
        
    def optimize_parameters(self, param_ranges: Dict) -> List[Dict]:
        """
        Optimiza parámetros usando grid search con procesamiento paralelo
        
        param_ranges: Diccionario con rangos de parámetros a optimizar
        Ejemplo:
        {
            'risk_per_trade': [0.5, 1.0, 1.5, 2.0],
            'atr_multiplier': [1.5, 2.0, 2.5, 3.0],
            'score_threshold': [60, 65, 70, 75]
        }
        """
        # Generar todas las combinaciones de parámetros
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        param_combinations = list(product(*param_values))
        
        # Ejecutar backtests en paralelo
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for params in param_combinations:
                param_dict = dict(zip(param_names, params))
                futures.append(
                    executor.submit(self._run_single_backtest, param_dict)
                )
            
            # Recolectar resultados
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    self.results.append(result)
        
        # Ordenar resultados por Sharpe Ratio
        self.results.sort(key=lambda x: x['metrics']['sharpe_ratio'], reverse=True)
        return self.results
        
    def _run_single_backtest(self, params: Dict) -> Dict:
        """Ejecuta un solo backtest con parámetros específicos"""
        try:
            backtester = Backtester(
                self.ticker,
                self.start_date,
                self.end_date,
                self.initial_capital
            )
            
            results = backtester.run_backtest(
                risk_per_trade=params.get('risk_per_trade', 1.0),
                atr_multiplier=params.get('atr_multiplier', 2.0)
            )
            
            if results:
                return {
                    'parameters': params,
                    'metrics': results
                }
            return None
            
        except Exception as e:
            print(f"Error en backtest con parámetros {params}: {str(e)}")
            return None
            
    def save_optimization_results(self, filename: str):
        """Guarda los resultados de la optimización en un archivo JSON"""
        if not self.results:
            return
            
        output = {
            'ticker': self.ticker,
            'period': {
                'start': self.start_date,
                'end': self.end_date
            },
            'initial_capital': self.initial_capital,
            'optimization_results': self.results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
            
def optimize_ticker_parameters(ticker: str, start_date: str, end_date: str,
                             initial_capital: float = 10000) -> Dict:
    """Función helper para optimizar parámetros de un ticker específico"""
    optimizer = ParameterOptimizer(ticker, start_date, end_date, initial_capital)
    
    # Definir rangos de parámetros a optimizar
    param_ranges = {
        'risk_per_trade': [0.5, 1.0, 1.5, 2.0],
        'atr_multiplier': [1.5, 2.0, 2.5, 3.0],
        'score_threshold': [60, 65, 70, 75]
    }
    
    results = optimizer.optimize_parameters(param_ranges)
    
    if results:
        filename = f"optimization_results_{ticker}_{start_date}_{end_date}.json"
        optimizer.save_optimization_results(filename)
        print(f"Optimización completada para {ticker}. Resultados guardados en {filename}")
        
        # Retornar los mejores parámetros
        best_result = results[0]
        return {
            'best_parameters': best_result['parameters'],
            'performance_metrics': best_result['metrics']
        }
    else:
        print(f"Error en la optimización para {ticker}")
        return None

if __name__ == "__main__":
    # Ejemplo de uso
    ticker = "AAPL"
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    
    best_params = optimize_ticker_parameters(ticker, start_date, end_date)
    if best_params:
        print("\nMejores Parámetros Encontrados:")
        print("Parámetros:", best_params['best_parameters'])
        print("\nMétricas de Rendimiento:")
        print(f"Retorno Total: {best_params['performance_metrics']['total_return']:.2f}%")
        print(f"Drawdown Máximo: {best_params['performance_metrics']['max_drawdown']:.2f}%")
        print(f"Ratio de Sharpe: {best_params['performance_metrics']['sharpe_ratio']:.2f}")
        print(f"Total de Operaciones: {best_params['performance_metrics']['total_trades']}")
        print(f"Operaciones Ganadoras: {best_params['performance_metrics']['winning_trades']}") 