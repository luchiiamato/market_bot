import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import json
from investment_recommendations import calcular_metricas_cedear, calcular_score_inversion, CEDEAR_MAPPING
from backtesting import Backtester
from optimizer import ParameterOptimizer
from quality_filters import QualityFilters

class MarketAnalyzer:
    def __init__(self, capital: float = 10000):
        self.capital = capital
        self.quality_filters = QualityFilters
        self.backtester = Backtester
        self.optimizer = ParameterOptimizer
        
    def analyze_ticker(self, ticker: str, start_date: str = None, end_date: str = None) -> Dict:
        """
        Analiza un ticker específico usando todos los componentes
        """
        try:
            print(f"\nIniciando análisis para {ticker}...")
            
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            if end_date is None:
                end_date = datetime.now().strftime("%Y-%m-%d")
                
            results = {}
            
            # 1. Verificar calidad del ticker
            print("Verificando filtros de calidad...")
            quality_results = self.quality_filters(ticker).check_all_filters()
            results['quality_analysis'] = quality_results
            
            # Si no pasa los filtros de calidad, retornar temprano
            if quality_results['overall_score'] < 0.6:
                print(f"Ticker {ticker} no cumple criterios de calidad mínimos")
                results['recommendation'] = "NO RECOMENDADO - No cumple criterios de calidad"
                return results
                
            # 2. Optimizar parámetros
            print("Optimizando parámetros...")
            optimizer = self.optimizer(ticker, start_date, end_date, self.capital)
            param_ranges = {
                'risk_per_trade': [0.5, 1.0, 1.5, 2.0],
                'atr_multiplier': [1.5, 2.0, 2.5, 3.0],
                'score_threshold': [60, 65, 70, 75]
            }
            optimization_results = optimizer.optimize_parameters(param_ranges)
            
            if optimization_results:
                best_params = optimization_results[0]['parameters']
                results['optimized_parameters'] = best_params
                print(f"Parámetros optimizados: {best_params}")
            else:
                results['optimized_parameters'] = {
                    'risk_per_trade': 1.0,
                    'atr_multiplier': 2.0,
                    'score_threshold': 70
                }
                print("Usando parámetros por defecto")
                
            # 3. Ejecutar backtest con parámetros optimizados
            print("Ejecutando backtest...")
            backtester = self.backtester(ticker, start_date, end_date, self.capital)
            backtest_results = backtester.run_backtest(
                risk_per_trade=results['optimized_parameters']['risk_per_trade'],
                atr_multiplier=results['optimized_parameters']['atr_multiplier']
            )
            
            if backtest_results:
                results['backtest_results'] = backtest_results
                print("Backtest completado exitosamente")
            else:
                results['backtest_results'] = None
                print("No se pudieron obtener resultados del backtest")
                
            # 4. Calcular métricas actuales
            print("Calculando métricas actuales...")
            current_metrics = calcular_metricas_cedear(ticker)
            if current_metrics:
                score, razones = calcular_score_inversion(current_metrics)
                current_metrics['score'] = score
                current_metrics['razones'] = razones
                results['current_metrics'] = current_metrics
                print(f"Score actual: {score}")
            else:
                results['current_metrics'] = None
                print("No se pudieron calcular métricas actuales")
                
            # 5. Generar recomendación final
            if results['current_metrics'] and results['backtest_results']:
                # Calcular score combinado
                quality_score = results['quality_analysis']['overall_score'] * 100
                backtest_score = results['backtest_results']['sharpe_ratio'] * 10
                current_score = results['current_metrics']['score']
                
                combined_score = (quality_score * 0.3 + backtest_score * 0.3 + current_score * 0.4)
                
                if combined_score >= 80:
                    recommendation = "FUERTE COMPRA"
                elif combined_score >= 70:
                    recommendation = "COMPRA"
                elif combined_score >= 60:
                    recommendation = "NEUTRAL"
                else:
                    recommendation = "NO RECOMENDADO"
                    
                results['recommendation'] = {
                    'action': recommendation,
                    'combined_score': combined_score,
                    'quality_score': quality_score,
                    'backtest_score': backtest_score,
                    'current_score': current_score
                }
                print(f"Recomendación generada: {recommendation}")
            else:
                results['recommendation'] = "NO RECOMENDADO - Datos insuficientes"
                print("No hay suficientes datos para generar recomendación")
                
            return results
            
        except Exception as e:
            print(f"Error analizando {ticker}: {str(e)}")
            return {
                'error': str(e),
                'recommendation': "ERROR - No se pudo completar el análisis"
            }
        
    def analyze_market(self, tickers: List[str] = None) -> Dict:
        """
        Analiza múltiples tickers y genera recomendaciones
        """
        if tickers is None:
            tickers = list(CEDEAR_MAPPING.keys())
            
        results = {}
        recommendations = []
        
        for ticker in tickers:
            print(f"\nAnalizando {ticker}...")
            ticker_results = self.analyze_ticker(ticker)
            results[ticker] = ticker_results
            
            rec = ticker_results.get('recommendation', {})
            if isinstance(rec, dict) and rec.get('action') in ['FUERTE COMPRA', 'COMPRA']:
                recommendations.append({
                    'ticker': ticker,
                    'recommendation': rec,
                    'current_metrics': ticker_results.get('current_metrics'),
                    'quality_score': ticker_results['quality_analysis']['overall_score']
                })
                
        # Ordenar recomendaciones por score combinado
        recommendations.sort(key=lambda x: x['recommendation']['combined_score'], reverse=True)
        
        # Generar reporte final
        final_report = {
            'fecha_analisis': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'capital_disponible': self.capital,
            'total_tickers_analizados': len(tickers),
            'recomendaciones': recommendations[:10],  # Top 10 recomendaciones
            'resumen_por_ticker': results
        }
        
        # Guardar reporte
        filename = f"market_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, indent=4, ensure_ascii=False)
            
        print(f"\nAnálisis completado. Reporte guardado en {filename}")
        return final_report

def main():
    # Ejemplo de uso
    analyzer = MarketAnalyzer(capital=10000)
    
    # Analizar mercado completo
    report = analyzer.analyze_market()
    
    # Crear un reporte más detallado
    detailed_report = {
        "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "capital_disponible": analyzer.capital,
        "top_recomendaciones": []
    }
    
    # Procesar las recomendaciones
    for i, rec in enumerate(report['recomendaciones'], 1):
        recomendacion = {
            "posicion": i,
            "ticker": rec['ticker'],
            "recomendacion": rec['recommendation']['action'],
            "scores": {
                "combinado": round(rec['recommendation']['combined_score'], 2),
                "calidad": round(rec['quality_score']*100, 2),
                "backtest": round(rec['recommendation']['backtest_score'], 2),
                "actual": round(rec['recommendation']['current_score'], 2)
            }
        }
        
        if rec.get('current_metrics'):
            recomendacion["metricas_actuales"] = {
                "precio": round(rec['current_metrics']['precio'], 2),
                "rsi": round(rec['current_metrics']['rsi'], 2),
                "tendencias": {
                    "corta": rec['current_metrics']['tendencia_corta'],
                    "media": rec['current_metrics']['tendencia_media'],
                    "larga": rec['current_metrics']['tendencia_larga']
                }
            }
        
        detailed_report["top_recomendaciones"].append(recomendacion)
    
    # Guardar el reporte detallado
    filename = f"analisis_detallado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(detailed_report, f, indent=4, ensure_ascii=False)
    
    print(f"\nReporte detallado guardado en: {filename}")

if __name__ == "__main__":
    main() 