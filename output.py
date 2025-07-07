import csv

def generar_reporte(df):
    with open("reporte_final.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Ticker", "Precio Actual", "Señal", "Razones", "Predicción", "Confianza", "Stop Loss", "Take Profit", "Sentimiento Neto"])
        for _, row in df.iterrows():
            writer.writerow([
                row["ticker"],
                row["precio"],
                row["senal"],
                "; ".join(row["razones"]),
                row["prediccion"],
                row["confianza"],
                row["stop_loss"],
                row["take_profit"],
                row["sentimiento"]
            ])