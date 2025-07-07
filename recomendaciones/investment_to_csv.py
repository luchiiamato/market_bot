import json
import csv

# Suponiendo que tu JSON está en una variable llamada data (podés leerlo desde archivo también)
with open("recomendaciones_inversion_20250521_180253.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Abrimos el archivo CSV para escritura
with open("recomendaciones.csv", mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file, quoting=csv.QUOTE_ALL)  # Usamos QUOTE_ALL para mejor legibilidad

    # Escribimos los encabezados
    writer.writerow([
        "orden_recomendado", "ticker", "score", "precio_actual", "tendencia_corta","tendencia_media","tendencia_larga", "rsi",
        "acciones_recomendadas", "inversion_total", "potencial_ganancia", "razones",
        "riesgo", "tiempo_recomendado_hold"
    ])

    # Escribimos cada recomendación como fila
    for rec in data["recomendaciones"]:
        writer.writerow([
            rec["orden_recomendado"],
            rec["ticker"],
            rec["score"],
            rec["precio_actual"],
            rec["tendencias"]["corta"],  # Usamos la tendencia corta como referencia
            rec["tendencias"]["media"],
            rec["tendencias"]["larga"],
            rec["rsi"],
            rec["acciones_recomendadas"],
            rec["inversion_total"],
            rec["potencial_ganancia"],
            "\n".join(rec["razones"]),  # Unimos las razones con saltos de línea
            rec["riesgo"],
            rec["tiempo_recomendado_hold"]
        ])

print("CSV generado exitosamente.")
