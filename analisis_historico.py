#!/usr/bin/env python3
"""
Procesador analítico de métricas: rankings provinciales y filtros de riesgos.
"""
import sys
import os
import pandas as pd

def correr_analisis(archivo_csv="riesgo_climatico.csv"):
    if not os.path.exists(archivo_csv):
        print(f"⚠ No se encontró el archivo {archivo_csv}")
        sys.exit(1)

    df = pd.read_csv(archivo_csv)
    print("\n--- RANKING DE SEGURIDAD POR PROVINCIA ---")
    resumen = df.groupby('provincia').agg(
        total_franjas=('nivel', 'count'),
        franjas_verdes=('nivel', lambda x: (x == 'VERDE').sum()),
        franjas_rojas=('nivel', lambda x: (x == 'ROJO').sum())
    ).reset_index()
    resumen['porcentaje_seguro'] = (resumen['franjas_verdes'] / resumen['total_franjas']) * 100
    resumen = resumen.sort_values(by=['porcentaje_seguro', 'franjas_rojas'], ascending=[False, True])
    print(resumen.to_string(index=False))

    print("\n--- RESUMEN ESPECÍFICO DE VISITAS CRÍTICAS EN PARANÁ ---")
    df_parana = df[df['localidad'].str.lower() == 'paraná']
    if not df_parana.empty:
        columnas = ['fecha', 'franja', 'nivel', 'prob_lluvia_max_pct', 'lluvia_mm', 'racha_max_kmh']
        print(df_parana[columnas].to_string(index=False))
    else:
        print("No se encontraron registros de la localidad 'Paraná'.")

if __name__ == "__main__":
    correr_analisis()
