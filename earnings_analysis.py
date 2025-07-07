import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

def obtener_historial_earnings(ticker: str) -> pd.DataFrame:
    """
    Obtiene el historial de earnings reportados para un ticker usando el income statement
    """
    try:
        stock = yf.Ticker(ticker)
        income_stmt = stock.income_stmt
        
        if income_stmt.empty:
            print(f"No hay datos de earnings disponibles para {ticker}")
            return pd.DataFrame()
            
        # Obtener la columna de Net Income y convertir a DataFrame
        earnings = pd.DataFrame({
            'Earnings': income_stmt.loc['Net Income']
        })
        
        # Convertir el índice a datetime si no lo es
        if not isinstance(earnings.index, pd.DatetimeIndex):
            earnings.index = pd.to_datetime(earnings.index)
            
        return earnings
        
    except Exception as e:
        print(f"Error obteniendo historial de earnings para {ticker}: {str(e)}")
        return pd.DataFrame()

def calcular_metricas_earnings(earnings: pd.DataFrame) -> Dict:
    """
    Calcula métricas relevantes del historial de earnings
    """
    if earnings.empty:
        return None
        
    try:
        # Convertir a numérico y eliminar nulos
        earnings['Earnings'] = pd.to_numeric(earnings['Earnings'], errors='coerce')
        earnings = earnings.dropna(subset=['Earnings'])
        
        if len(earnings) < 2:
            print("No hay suficientes datos de earnings para calcular métricas.")
            return None
        
        # Calcular métricas básicas
        earnings_actuales = earnings['Earnings'].iloc[-1]
        earnings_anteriores = earnings['Earnings'].iloc[-2]
        cambio_earnings = ((earnings_actuales - earnings_anteriores) / abs(earnings_anteriores)) * 100
        
        # Calcular tendencia de earnings
        earnings_ultimos_4 = earnings['Earnings'].iloc[-4:]
        tendencia_earnings = np.polyfit(range(len(earnings_ultimos_4)), earnings_ultimos_4, 1)[0]
        
        # Calcular volatilidad de earnings
        volatilidad_earnings = earnings['Earnings'].std()
        
        # Calcular consistencia (cuántas veces superó expectativas)
        if 'Expected' in earnings.columns:
            supero_expectativas = (earnings['Earnings'] > earnings['Expected']).sum()
            total_reportes = len(earnings)
            tasa_superacion = (supero_expectativas / total_reportes) * 100
        else:
            tasa_superacion = None
            
        return {
            'earnings_actuales': float(earnings_actuales),
            'earnings_anteriores': float(earnings_anteriores),
            'cambio_earnings': float(cambio_earnings),
            'tendencia_earnings': float(tendencia_earnings),
            'volatilidad_earnings': float(volatilidad_earnings),
            'tasa_superacion': tasa_superacion
        }
        
    except Exception as e:
        print(f"Error calculando métricas de earnings: {str(e)}")
        return None

def analisis_cortoplacista_earnings(ticker, metricas, hist, earnings):
    """
    Analiza la reacción del precio tras los últimos 4 earnings y da una recomendación clara de trading a corto plazo.
    """
    # Asegurar que ambos índices sean naive (sin zona horaria)
    if hist.index.tz is not None:
        hist = hist.copy()
        hist.index = hist.index.tz_convert(None)
    resumen_reaccion = []
    fechas = earnings.index[-4:]
    for fecha in fechas:
        fecha = pd.to_datetime(fecha)
        if fecha.tzinfo is not None:
            fecha = fecha.tz_convert(None)
        # Buscar el día hábil anterior
        idx_antes = hist.index[hist.index < fecha]
        idx_despues = hist.index[hist.index > fecha]
        try:
            if len(idx_antes) == 0 or len(idx_despues) == 0:
                raise Exception('No hay datos de mercado cercanos')
            precio_antes = hist.loc[idx_antes[-1]]['Close']
            precio_despues = hist.loc[idx_despues[0]]['Close']
            variacion = ((precio_despues - precio_antes) / precio_antes) * 100
            resumen_reaccion.append({
                'fecha': fecha.strftime('%Y-%m-%d'),
                'precio_antes': float(precio_antes),
                'precio_despues': float(precio_despues),
                'variacion_pct': float(variacion),
                'reaccion': 'SUBE' if variacion > 0 else 'BAJA'
            })
        except Exception:
            resumen_reaccion.append({
                'fecha': fecha.strftime('%Y-%m-%d'),
                'precio_antes': None,
                'precio_despues': None,
                'variacion_pct': None,
                'reaccion': 'SIN DATOS'
            })
    # Lógica de recomendación
    tendencia = metricas['tendencia_earnings']
    tasa_superacion = metricas['tasa_superacion']
    volatilidad = metricas['volatilidad_earnings']
    explicacion = ""
    recomendacion = ""
    if tendencia > 0 and tasa_superacion and tasa_superacion > 60:
        recomendacion = "Comprar antes del reporte y vender tras el earnings."
        explicacion = "La empresa muestra tendencia positiva y suele superar expectativas. Históricamente, el precio suele reaccionar bien tras los earnings."
    elif tendencia > 0 and (not tasa_superacion or tasa_superacion <= 60):
        recomendacion = "Esperar el reporte. Si hay caída fuerte, comprar tras el earnings."
        explicacion = "Aunque la tendencia es positiva, la empresa no suele sorprender al alza. Mejor esperar la reacción del mercado."
    elif tendencia <= 0 and tasa_superacion and tasa_superacion < 50:
        recomendacion = "Vender antes del reporte o buscar oportunidad tras la caída."
        explicacion = "Tendencia negativa y baja tasa de superación de expectativas. El riesgo de caída es alto."
    else:
        recomendacion = "Alto riesgo, operar solo si tienes experiencia en trading de volatilidad."
        explicacion = "La situación es incierta o muy volátil. Mejor evitar operar salvo que busques riesgo."
    if volatilidad > abs(metricas['earnings_actuales'] * 0.2):
        explicacion += " Ojo: la volatilidad de los earnings es muy alta, el movimiento puede ser brusco."
    return {
        'recomendacion_corto_plazo': recomendacion,
        'explicacion_corto_plazo': explicacion,
        'resumen_reaccion_ultimos_earnings': resumen_reaccion
    }

def predecir_earnings_futuros(ticker: str) -> Dict:
    """
    Predice los próximos earnings basado en múltiples factores
    """
    try:
        # Obtener datos históricos (ahora 5 años)
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5y")
        if hist.empty:
            return None
        # Obtener historial de earnings
        earnings = obtener_historial_earnings(ticker)
        if earnings.empty:
            return None
        # Calcular métricas de earnings
        metricas = calcular_metricas_earnings(earnings)
        if not metricas:
            return None
        # Obtener datos fundamentales
        info = stock.info
        # Obtener calendario de earnings
        calendar = stock.calendar
        fecha_proximo_earning = None
        valor_esperado = None
        # Soportar DataFrame o dict
        if isinstance(calendar, pd.DataFrame):
            if not calendar.empty:
                if 'Earnings Date' in calendar.index:
                    fecha_proximo_earning = str(calendar.loc['Earnings Date'][0])
                if 'Earnings Average' in calendar.index:
                    valor_esperado = calendar.loc['Earnings Average'][0]
        elif isinstance(calendar, dict):
            if 'Earnings Date' in calendar:
                fecha_proximo_earning = str(calendar['Earnings Date'])
            if 'Earnings Average' in calendar:
                valor_esperado = calendar['Earnings Average']
        # Calcular score de predicción
        score = 0
        razones = []
        # Factor 1: Tendencia de earnings
        if metricas['tendencia_earnings'] > 0:
            score += 25
            razones.append("Tendencia positiva de earnings")
        else:
            score += 10
            razones.append("Tendencia negativa de earnings")
        # Factor 2: Consistencia en superar expectativas
        if metricas['tasa_superacion'] and metricas['tasa_superacion'] > 70:
            score += 25
            razones.append(f"Alta tasa de superación de expectativas ({metricas['tasa_superacion']:.1f}%)")
        elif metricas['tasa_superacion'] and metricas['tasa_superacion'] > 50:
            score += 15
            razones.append(f"Tasa moderada de superación de expectativas ({metricas['tasa_superacion']:.1f}%)")
        else:
            score += 5
            razones.append("Baja tasa de superación de expectativas")
        # Factor 3: Crecimiento de ingresos
        if 'revenueGrowth' in info and info['revenueGrowth']:
            if info['revenueGrowth'] > 0.1:  # 10% de crecimiento
                score += 20
                razones.append(f"Fuerte crecimiento de ingresos ({info['revenueGrowth']*100:.1f}%)")
            elif info['revenueGrowth'] > 0:
                score += 10
                razones.append(f"Crecimiento moderado de ingresos ({info['revenueGrowth']*100:.1f}%)")
            else:
                score += 5
                razones.append("Crecimiento negativo de ingresos")
        # Factor 4: Margen de beneficio
        if 'profitMargins' in info and info['profitMargins']:
            if info['profitMargins'] > 0.2:  # 20% de margen
                score += 15
                razones.append(f"Alto margen de beneficio ({info['profitMargins']*100:.1f}%)")
            elif info['profitMargins'] > 0.1:  # 10% de margen
                score += 10
                razones.append(f"Margen de beneficio moderado ({info['profitMargins']*100:.1f}%)")
            else:
                score += 5
                razones.append("Margen de beneficio bajo")
        # Factor 5: Volatilidad de earnings
        if metricas['volatilidad_earnings'] < abs(metricas['earnings_actuales'] * 0.1):  # Menos del 10% de volatilidad
            score += 15
            razones.append("Baja volatilidad en earnings")
        else:
            score += 5
            razones.append("Alta volatilidad en earnings")
        # Determinar probabilidad de buenos earnings
        probabilidad = "ALTA" if score >= 70 else "MEDIA" if score >= 50 else "BAJA"
        # --- Análisis cortoplacista ---
        analisis_corto = analisis_cortoplacista_earnings(ticker, metricas, hist, earnings)
        # Mostrar en consola
        print(f"\nRECOMENDACIÓN CORTO PLAZO para {ticker}: {analisis_corto['recomendacion_corto_plazo']}")
        print(f"Explicación: {analisis_corto['explicacion_corto_plazo']}")
        print("Reacción del precio tras los últimos 4 earnings:")
        for r in analisis_corto['resumen_reaccion_ultimos_earnings']:
            if r['variacion_pct'] is not None:
                print(f"  {r['fecha']}: {r['reaccion']} ({r['variacion_pct']:.2f}%)")
            else:
                print(f"  {r['fecha']}: {r['reaccion']} (sin datos)")
        if fecha_proximo_earning:
            print(f"Próxima fecha de earnings: {fecha_proximo_earning}")
        if valor_esperado is not None:
            print(f"Valor esperado por el mercado: {valor_esperado}")
        return {
            'ticker': ticker,
            'score': score,
            'probabilidad': probabilidad,
            'razones': razones,
            'metricas': metricas,
            'recomendacion_corto_plazo': analisis_corto['recomendacion_corto_plazo'],
            'explicacion_corto_plazo': analisis_corto['explicacion_corto_plazo'],
            'resumen_reaccion_ultimos_earnings': analisis_corto['resumen_reaccion_ultimos_earnings'],
            'fecha_proximo_earning': fecha_proximo_earning,
            'valor_esperado': valor_esperado
        }
    except Exception as e:
        print(f"Error prediciendo earnings para {ticker}: {str(e)}")
        return None

def generar_reporte_earnings(tickers: List[str]):
    """
    Genera un reporte de análisis de earnings para una lista de tickers
    """
    reporte = {
        "fecha_generacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analisis": []
    }
    
    for ticker in tickers:
        print(f"\nAnalizando earnings para {ticker}...")
        prediccion = predecir_earnings_futuros(ticker)
        
        if prediccion:
            reporte["analisis"].append(prediccion)
            
    # Guardar el reporte
    nombre_archivo = f"analisis_earnings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(f'recomendaciones/{nombre_archivo}', 'w', encoding='utf-8') as f:
        json.dump(reporte, f, indent=4, ensure_ascii=False)
        
    print(f"\nReporte de earnings generado exitosamente: {nombre_archivo}")
    print("⚠️ ADVERTENCIA: Este análisis es solo informativo y no constituye asesoramiento financiero.")

if __name__ == "__main__":
    # Ejemplo de uso
    tickers = ['NVDA']
    generar_reporte_earnings(tickers) 