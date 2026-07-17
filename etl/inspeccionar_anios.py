"""
Inspector de archivos anuales del SIES.

Antes de escribir una sola línea de análisis longitudinal hay que saber qué trae cada año.
El SIES cambió columnas, categorías y fechas de corte a lo largo del tiempo, y ninguna de esas
cosas viene documentada en el archivo.

USO
    1. Baja los archivos anuales de matrícula desde mifuturo.cl/sies (sección Bases de datos)
       o desde datosabiertos.mineduc.cl/matricula-en-educacion-superior/
    2. Déjalos todos en data/raw/ con el nombre tal como vienen.
    3. python etl/inspeccionar_anios.py

QUÉ RESPONDE
    - Qué columnas trae cada año y cuáles aparecen o desaparecen.
    - Desde cuándo existe MODALIDAD, TIPO DE PLAN y ÁREA CARRERA GENÉRICA.
    - Si las categorías de esas columnas se mantienen o cambian de nombre.
    - Cuántas instituciones hay cada año y cuáles entran o salen.
    - Encoding, separador y fecha de corte de cada archivo.

No transforma nada. Solo mira y reporta.
"""

import re
import sys
from pathlib import Path

import pandas as pd

RAW = Path('data/raw')

# Columnas que deciden si el análisis longitudinal es posible o no.
CRITICAS = [
    'MODALIDAD',
    'TIPO DE PLAN DE LA CARRERA',
    'ÁREA CARRERA GENÉRICA',
    'JORNADA',
    'NIVEL GLOBAL',
    'TOTAL MATRÍCULA',
    'TOTAL MATRÍCULA PRIMER AÑO',
    'CINE-F 2013 ÁREA',
    'ÁREA DEL CONOCIMIENTO',
    'NOMBRE INSTITUCIÓN',
    'REGIÓN',
]


def sniff(path):
    """Detecta encoding y separador probando las combinaciones que usa el SIES."""
    for enc in ['latin-1', 'utf-8', 'utf-8-sig']:
        for sep in [';', ',', '\t']:
            try:
                d = pd.read_csv(path, sep=sep, encoding=enc, nrows=5)
                if d.shape[1] > 5:
                    return enc, sep
            except Exception:
                continue
    return None, None


def anio_de(nombre):
    """Saca el año del nombre del archivo. Ojo: es una heurística, no un dato del archivo."""
    m = re.findall(r'(20\d{2})', nombre)
    return int(m[0]) if m else None


def inspeccionar(path):
    enc, sep = sniff(path)
    if enc is None:
        return {'archivo': path.name, 'error': 'no se pudo leer'}

    d = pd.read_csv(path, sep=sep, encoding=enc, low_memory=False)
    d.columns = [c.strip() for c in d.columns]

    col_anio = next((c for c in d.columns if c.strip().upper() in ('AÑO', 'ANIO', 'ANO', 'CAT_PERIODO')), None)
    valor_anio = d[col_anio].dropna().unique()[:2].tolist() if col_anio else None

    inst = next((c for c in d.columns if 'NOMBRE' in c and 'INSTITUC' in c), None)

    return {
        'archivo': path.name,
        'año_nombre': anio_de(path.name),
        'año_columna': valor_anio,
        'encoding': enc,
        'sep': sep,
        'filas': len(d),
        'columnas': d.shape[1],
        'instituciones': d[inst].nunique() if inst else None,
        'matrícula': int(d['TOTAL MATRÍCULA'].sum()) if 'TOTAL MATRÍCULA' in d else None,
        '_cols': set(d.columns),
        '_df': d,
    }


def main():
    if not RAW.exists():
        print(f'No existe {RAW}/. Créala y deja ahí los archivos anuales del SIES.')
        sys.exit(1)

    archivos = sorted([p for p in RAW.iterdir() if p.suffix.lower() in ('.csv', '.txt')])
    if not archivos:
        print(f'{RAW}/ está vacía. Baja los archivos desde mifuturo.cl/sies.')
        sys.exit(1)

    print(f'{len(archivos)} archivo(s) en {RAW}/\n')
    infos = [inspeccionar(p) for p in archivos]
    infos = [i for i in infos if 'error' not in i]
    infos.sort(key=lambda i: i['año_nombre'] or 0)

    # ── 1. resumen por archivo ───────────────────────────────────────────────
    print('=' * 78)
    print('1. QUÉ TRAE CADA ARCHIVO')
    print('=' * 78)
    resumen = pd.DataFrame([{k: v for k, v in i.items() if not k.startswith('_')} for i in infos])
    print(resumen.to_string(index=False))
    print()
    print('Verifica que "año_nombre" y "año_columna" coincidan. Si no, el nombre del archivo miente')
    print('y hay que tomar el año de la columna.')
    print()

    # ── 2. columnas críticas por año ─────────────────────────────────────────
    print('=' * 78)
    print('2. COLUMNAS CRÍTICAS — ¿desde cuándo existe cada una?')
    print('=' * 78)
    tabla = pd.DataFrame(
        {i['año_nombre']: {c: ('sí' if c in i['_cols'] else '—') for c in CRITICAS} for i in infos}
    )
    print(tabla.to_string())
    print()
    print('Un "—" en MODALIDAD marca hasta dónde llega la serie de modalidad. Antes de eso, lo')
    print('online venía como jornada "A Distancia" y hay que reconstruirlo por ahí.')
    print()

    # ── 3. columnas que aparecen o desaparecen ───────────────────────────────
    print('=' * 78)
    print('3. CAMBIOS DE ESQUEMA ENTRE AÑOS CONSECUTIVOS')
    print('=' * 78)
    for a, b in zip(infos, infos[1:]):
        nuevas = sorted(b['_cols'] - a['_cols'])
        idas   = sorted(a['_cols'] - b['_cols'])
        if nuevas or idas:
            print(f"\n{a['año_nombre']} → {b['año_nombre']}")
            if nuevas:
                print(f"  aparecen ({len(nuevas)}): {', '.join(nuevas[:8])}{' …' if len(nuevas) > 8 else ''}")
            if idas:
                print(f"  se van   ({len(idas)}): {', '.join(idas[:8])}{' …' if len(idas) > 8 else ''}")
        else:
            print(f"\n{a['año_nombre']} → {b['año_nombre']}: sin cambios de columnas")
    print()

    # ── 4. categorías de las variables de corte ──────────────────────────────
    print('=' * 78)
    print('4. ¿CAMBIAN LAS CATEGORÍAS? (si un nombre cambia, la serie se parte sin avisar)')
    print('=' * 78)
    for col in ['MODALIDAD', 'JORNADA', 'TIPO DE PLAN DE LA CARRERA', 'NIVEL GLOBAL']:
        print(f'\n--- {col}')
        for i in infos:
            if col in i['_cols']:
                cats = sorted(i['_df'][col].dropna().astype(str).str.strip().unique())
                print(f"  {i['año_nombre']}: {cats}")
            else:
                print(f"  {i['año_nombre']}: (no existe)")
    print()

    # ── 5. instituciones que entran y salen ──────────────────────────────────
    print('=' * 78)
    print('5. INSTITUCIONES QUE ENTRAN Y SALEN')
    print('=' * 78)
    print('Importa: si una universidad cierra, la participación de las demás sube sola. Un alza')
    print('de share puede ser un competidor que desapareció, no una victoria.')
    for a, b in zip(infos, infos[1:]):
        col = next((c for c in a['_cols'] if 'NOMBRE' in c and 'INSTITUC' in c), None)
        if not col or col not in b['_cols']:
            continue
        ia = set(a['_df'][col].dropna().unique())
        ib = set(b['_df'][col].dropna().unique())
        print(f"\n{a['año_nombre']} → {b['año_nombre']}")
        print(f"  entran ({len(ib - ia)}): {', '.join(sorted(ib - ia)[:6]) or '—'}")
        print(f"  salen  ({len(ia - ib)}): {', '.join(sorted(ia - ib)[:6]) or '—'}")
    print()

    # ── 6. área genérica: la llave del análisis competitivo ──────────────────
    print('=' * 78)
    print('6. ÁREA CARRERA GENÉRICA — la llave con la que se arman los mercados')
    print('=' * 78)
    col = 'ÁREA CARRERA GENÉRICA'
    conjuntos = {}
    for i in infos:
        if col in i['_cols']:
            conjuntos[i['año_nombre']] = set(i['_df'][col].dropna().astype(str).str.strip().unique())
            print(f"  {i['año_nombre']}: {len(conjuntos[i['año_nombre']])} categorías")
        else:
            print(f"  {i['año_nombre']}: (no existe) → sin esta columna no hay mercados comparables")
    if len(conjuntos) > 1:
        años = sorted(conjuntos)
        est = set.intersection(*conjuntos.values())
        print(f'\n  Estables en todos los años: {len(est)}')
        for a, b in zip(años, años[1:]):
            n, s = conjuntos[b] - conjuntos[a], conjuntos[a] - conjuntos[b]
            if n or s:
                print(f'  {a} → {b}: aparecen {len(n)}, se van {len(s)}')
                if n: print(f'      + {", ".join(sorted(n)[:5])}')
                if s: print(f'      - {", ".join(sorted(s)[:5])}')
    print()
    print('=' * 78)
    print('Con esto ya se sabe hasta dónde estira la serie y qué hay que armonizar.')
    print('=' * 78)


if __name__ == '__main__':
    main()
