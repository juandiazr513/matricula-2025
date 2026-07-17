"""
ETL de la serie histórica — Matrícula SIES 2015-2025.

Entrada : el archivo histórico del SIES (Matricula_2007_2025_WEB_*.csv), 264.258 filas, 145 MB.
Salida  : data/serie_2015_2025.csv, agregado, ~1 MB comprimido, apto para el navegador.

POR QUÉ 2015 Y NO 2017
    El Plan Regular de Continuidad nace en 2015 (26 alumnos en todo el país). Partir en 2017 se
    pierde su nacimiento, y hoy es un quinto del pregrado online. Además 2015-2019 deja cinco años
    de línea base pre-pandemia, que es lo que permite decir si el salto de 2020 rompió una
    tendencia o la continuó.
    Cambiar el rango es una línea: ANIO_INICIO.

POR QUÉ NO ANTES DE 2011
    MODALIDAD solo existe desde 2011. Antes hay que reconstruir lo online desde JORNADA. Además
    el Plan Especial de 2007 salta de 6.568 a 1.163 alumnos en un año, con el 69% concentrado en
    una sola universidad: es una reclasificación, no una fuga.

POR QUÉ SE AGREGA
    La vista de evolución no necesita el detalle de carrera y sede. Agregando por año, institución,
    área genérica, región, jornada, modalidad, tipo de plan y nivel, las 167.244 filas del período
    bajan a 102.641 sin perder un solo alumno, y el archivo pasa de 145 MB a 1 MB comprimido.
"""

import os
import sys
from pathlib import Path

import pandas as pd

ANIO_INICIO = 2015
SALIDA = Path('data/serie_2015_2025.csv')

CANDIDATOS = [
    Path('data/raw/Matricula_2007_2025_WEB_15_07_2025.csv'),
    Path('/mnt/user-data/uploads/Matricula_2007_2025_WEB_15_07_2025.csv'),
]

REN = {
    'AÑO': 'anio',
    'NOMBRE INSTITUCIÓN': 'institucion',
    'CLASIFICACIÓN INSTITUCIÓN NIVEL 1': 'tipo_inst',
    'CLASIFICACIÓN INSTITUCIÓN NIVEL 2': 'inst_n2',
    'REGIÓN': 'region',
    'ÁREA CARRERA GENÉRICA': 'area_generica',
    'ÁREA DEL CONOCIMIENTO': 'area',
    'CINE-F 2013 ÁREA': 'cine_area',
    'NIVEL GLOBAL': 'nivel_global',
    'JORNADA': 'jornada',
    'MODALIDAD': 'modalidad',
    'TIPO DE PLAN DE LA CARRERA': 'tipo_plan',
    'TOTAL MATRÍCULA': 'mat_total',
    'TOTAL MATRÍCULA PRIMER AÑO': 'mat1_total',
}

LLAVE = ['anio', 'institucion', 'tipo_inst', 'inst_n2', 'region', 'area_generica',
         'area', 'cine_area', 'nivel_global', 'jornada', 'modalidad', 'tipo_plan']


def main():
    src = next((p for p in CANDIDATOS if p.exists()), None)
    if src is None:
        print('No se encontró el archivo histórico del SIES.')
        print('Bájalo de mifuturo.cl/sies y déjalo en data/raw/.')
        sys.exit(1)

    print(f'Leyendo {src} …')
    d = pd.read_csv(src, sep=';', encoding='latin-1', low_memory=False)
    d.columns = [c.strip() for c in d.columns]
    d = d[list(REN)].rename(columns=REN)

    d['anio'] = d.anio.str[-4:].astype('int16')
    total_original = int(d[d.anio >= ANIO_INICIO].mat_total.sum())
    d = d[d.anio >= ANIO_INICIO]

    for c in d.select_dtypes(include='object').columns:
        d[c] = d[c].astype(str).str.strip()

    # MODALIDAD solo existe desde 2011; antes hay que reconstruirla desde JORNADA.
    # La equivalencia está verificada: en los 15 años donde ambas conviven (2011-2025), la jornada
    # "A Distancia" y la modalidad "No Presencial" dan cifras idénticas, sin una sola excepción.
    falta = d.modalidad.isin(['nan', ''])
    if falta.any():
        d.loc[falta, 'modalidad'] = d.loc[falta, 'jornada'].map(
            {'A Distancia': 'No Presencial'}).fillna('Presencial')
        print(f'  MODALIDAD reconstruida desde JORNADA en {falta.sum():,} filas')

    # Primer año no se rellena con cero: el SIES no escribe ceros en esa columna, escribe vacío,
    # y los Planes de Continuidad vienen 100% vacíos pese a tener matrícula. Ver etl/prep.py.
    d['mat_total'] = d.mat_total.fillna(0).astype('int32')
    d['mat1_total'] = d.mat1_total.astype('Int32')

    g = (d.groupby(LLAVE, dropna=False, observed=True)
           .agg(mat_total=('mat_total', 'sum'),
                mat1_total=('mat1_total', 'sum'),
                carreras=('mat_total', 'size'))
           .reset_index())
    g['mat1_total'] = g.mat1_total.astype('Int32')

    # ── validación ────────────────────────────────────────────────────────────
    chk = {
        'años': f'{g.anio.min()}–{g.anio.max()}',
        'filas_entrada': len(d),
        'filas_salida': len(g),
        'reducción_%': round((1 - len(g) / len(d)) * 100, 1),
        'matrícula_preservada': int(g.mat_total.sum()) == total_original,
        'instituciones_2015': int(g[g.anio == ANIO_INICIO].institucion.nunique()),
        'instituciones_2025': int(g[g.anio == 2025].institucion.nunique()),
    }
    for k, v in chk.items():
        print(f'  {k:<24} {v}')
    assert chk['matrícula_preservada'], 'La agregación perdió matrícula'

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    g.to_csv(SALIDA, index=False, encoding='utf-8')
    os.system(f'gzip -9 -kf {SALIDA}')
    mb = os.path.getsize(SALIDA) / 1024 / 1024
    kb = os.path.getsize(f'{SALIDA}.gz') / 1024
    os.remove(f'{SALIDA}.gz')
    print(f'\n{SALIDA}: {mb:.1f} MB  →  {kb:.0f} KB servido con gzip')

    # ── contraste con el corte 2025 ───────────────────────────────────────────
    p25 = Path('data/matricula2025.csv')
    if p25.exists():
        m = pd.read_csv(p25).mat_total.sum()
        s = g[g.anio == 2025].mat_total.sum()
        print(f'\nMatrícula 2025 — serie: {s:,} | corte independiente: {m:,} | calza: {s == m}')


if __name__ == '__main__':
    main()
