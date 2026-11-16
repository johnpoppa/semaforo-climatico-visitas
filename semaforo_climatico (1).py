#!/usr/bin/env python3
"""
Semáforo climático para agenda de visitas técnicas (Open-Meteo).

Consulta el pronóstico a 3 días por localidad, lo resume por día y franja
(mañana / tarde), calcula un nivel de riesgo (VERDE / AMARILLO / ROJO)
y compara los resultados con la ejecución previa para detectar cambios.
"""
import argparse
import sys
import time
import os
import pandas as pd
import requests

API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "America/Argentina/Buenos_Aires"
BATCH_SIZE = 50
FRANJAS = {"manana": (8, 13), "tarde": (14, 19)}
UMBRALES = {
    "prob_amarillo": 30,
    "prob_rojo": 60,
    "mm_amarillo": 1.0,
    "mm_rojo": 5.0,
    "racha_amarillo": 40,
    "racha_rojo": 60,
}
CODIGOS_TORMENTA = {95, 96, 99}

LOCALIDADES_EJEMPLO = [
    ("Córdoba", "Córdoba", -31.4201, -64.1888),
    ("Córdoba", "Río Cuarto", -33.1307, -64.3499),
    ("Buenos Aires", "CABA", -34.6037, -58.3816),
    ("Buenos Aires", "La Plata", -34.9205, -57.9536),
    ("Santa Fe", "Rosario", -32.9442, -60.6505),
    ("Santa Fe", "Santa Fe", -31.6333, -60.7000),
    ("Mendoza", "Mendoza", -32.8895, -68.8458),
    ("Tucumán", "San Miguel de Tucumán", -26.8083, -65.2176),
    ("Salta", "Salta", -24.7821, -65.4232),
    ("Entre Ríos", "Paraná", -31.7333, -60.5333),
    ("Misiones", "Posadas", -27.3671, -55.8961),
    ("Neuquén", "Neuquén", -38.9516, -68.0591),
]

NIVEL_ORDEN = {"VERDE": 0, "AMARILLO": 1, "ROJO": 2}

def cargar_localidades(path):
    if path and os.path.exists(path):
        df = pd.read_csv(path)
        return df
    return pd.DataFrame(LOCALIDADES_EJEMPLO, columns=["provincia", "localidad", "lat", "lon"])

def consultar_batch(batch, dias):
    params = {
        "latitude": ",".join(str(x) for x in batch["lat"]),
        "longitude": ",".join(str(x) for x in batch["lon"]),
        "hourly": "precipitation_probability,precipitation,wind_gusts_10m,weather_code",
        "forecast_days": dias,
        "timezone": TIMEZONE,
        "wind_speed_unit": "kmh",
    }
    for intento in range(3):
        try:
            r = requests.get(API_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else [data]
        except Exception as e:
            print(f"  Error de red: {e}", file=sys.stderr)
            time.sleep(2)
    sys.exit("No se pudo consultar Open-Meteo.")

def nivel_riesgo(prob, mm, racha, tormenta):
    u = UMBRALES
    if tormenta or prob > u["prob_rojo"] or mm > u["mm_rojo"] or racha >= u["racha_rojo"]:
        return "ROJO"
    if prob >= u["prob_amarillo"] or mm >= u["mm_amarillo"] or racha >= u["racha_amarillo"]:
        return "AMARILLO"
    return "VERDE"

def resumir(loc, resp):
    h = pd.DataFrame(resp["hourly"])
    h["time"] = pd.to_datetime(h["time"])
    h["fecha"] = h["time"].dt.date
    h["hora"] = h["time"].dt.hour

    filas = []
    for fecha, dia in h.groupby("fecha"):
        for franja, (ini, fin) in FRANJAS.items():
            t = dia[(dia["hora"] >= ini) & (dia["hora"] <= fin)]
            if t.empty: continue
            prob = float(t["precipitation_probability"].max())
            mm = float(t["precipitation"].sum())
            racha = float(t["wind_gusts_10m"].max())
            tormenta = bool(t["weather_code"].isin(CODIGOS_TORMENTA).any())
            filas.append({
                "provincia": loc["provincia"],
                "localidad": loc["localidad"],
                "lat": loc["lat"],
                "lon": loc["lon"],
                "fecha": str(fecha),
                "franja": franja,
                "prob_lluvia_max_pct": round(prob, 0),
                "lluvia_mm": round(mm, 1),
                "racha_max_kmh": round(racha, 0),
                "tormenta_electrica": tormenta,
                "nivel": nivel_riesgo(prob, mm, racha, tormenta),
            })
    return filas

def detectar_cambios_significativos(archivo_anterior, archivo_nuevo):
    if not os.path.exists(archivo_anterior):
        return []
    previo = pd.read_csv(archivo_anterior)
    nuevo = pd.read_csv(archivo_nuevo)
    comparativa = pd.merge(previo, nuevo, on=['fecha', 'localidad', 'franja'], suffixes=('_previo', '_nuevo'))
    
    alertas = []
    nivel_map = {'VERDE': 0, 'AMARILLO': 1, 'ROJO': 2}
    for _, fila in comparativa.iterrows():
        nivel_pre = nivel_map.get(fila['nivel_previo'], 0)
        nivel_nue = nivel_map.get(fila['nivel_nuevo'], 0)
        if nivel_nue > nivel_pre:
            alertas.append(f"🚨 RIESGO EMPEORÓ: {fila['localidad']} ({fila['fecha']} - {fila['franja']}): de {fila['nivel_previo']} a {fila['nivel_nuevo']}.")
        elif (fila['prob_lluvia_max_pct_nuevo'] - fila['prob_lluvia_max_pct_previo']) >= 30:
            alertas.append(f"⚠️ LLUVIA EN ALZA: {fila['localidad']} ({fila['fecha']} - {fila['franja']}): probabilidad subió de {fila['prob_lluvia_max_pct_previo']}% a {fila['prob_lluvia_max_pct_nuevo']}%.")
    return alertas

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--localidades", default=None)
    ap.add_argument("--dias", type=int, default=3)
    ap.add_argument("--salida", default="riesgo_climatico.csv")
    args = ap.parse_args()

    archivo_previo = args.salida.replace(".csv", "_previo.csv")
    if os.path.exists(args.salida):
        if os.path.exists(archivo_previo): os.remove(archivo_previo)
        os.rename(args.salida, archivo_previo)

    locs = cargar_localidades(args.localidades)
    filas = []
    for i in range(0, len(locs), BATCH_SIZE):
        batch = locs.iloc[i:i + BATCH_SIZE]
        respuestas = consultar_batch(batch, args.dias)
        for (_, loc), resp in zip(batch.iterrows(), respuestas):
            filas.extend(resumir(loc, resp))

    df = pd.DataFrame(filas)
    df["orden"] = df["nivel"].map(NIVEL_ORDEN)
    df = df.sort_values(["fecha", "orden", "provincia", "localidad", "franja"], ascending=[True, False, True, True, True]).drop(columns="orden")
    df.to_csv(args.salida, index=False, encoding="utf-8-sig")
    print(f"💾 Archivo guardado correctamente en: {args.salida}")

    alertas_cambios = detectar_cambios_significativos(archivo_previo, args.salida)
    if alertas_cambios:
        print("\n=== ⚠️ ALERTAS DE CAMBIOS ===")
        for a in alertas_cambios:
            print(a)
    else:
        print("\n✅ Sin alertas frente a la última medición.")

if __name__ == "__main__":
    main()
