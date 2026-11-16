#!/usr/bin/env python3
"""
Generador de Reporte Visual en formato Imagen PNG.
"""
import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def generar_grafica(archivo_csv="riesgo_climatico.csv", output_img="distribucion_alertas.png"):
    if not os.path.exists(archivo_csv):
        print(f"⚠ Error: No se encontró el archivo {archivo_csv}")
        sys.exit(1)

    df_riesgos = pd.read_csv(archivo_csv)
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(12, 7))

    order_riesgos = ['VERDE', 'AMARILLO', 'ROJO']
    colores = {'VERDE': '#2ca02c', 'AMARILLO': '#ff7f0e', 'ROJO': '#d62728'}

    ax = sns.countplot(
        data=df_riesgos,
        x='localidad',
        hue='nivel',
        hue_order=order_riesgos,
        palette=colores
    )

    plt.title('Distribución de Alertas Climáticas por Localidad (Próximos 3 días)', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('Localidad', fontsize=11, labelpad=10)
    plt.ylabel('Cantidad de Franjas Horarias', fontsize=11, labelpad=10)
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.legend(title='Nivel de Riesgo', fontsize=10, title_fontsize=11)

    for container in ax.containers:
        ax.bar_label(container, fmt='%d', label_type='edge', padding=2, fontsize=8)

    plt.tight_layout()
    plt.savefig(output_img, dpi=150)
    print(f"📊 Gráfica exportada con éxito como: {output_img}")

if __name__ == "__main__":
    generar_grafica()
