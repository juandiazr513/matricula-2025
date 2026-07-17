"""
Motor de análisis de mercados — Matrícula SIES 2025.

Réplica en pandas de la lógica que `assets/app.js` ejecuta en el navegador. Vive acá y no dentro
de los notebooks para que exista una sola implementación: cuando un criterio cambia —como pasó con
el desempate y con el umbral de liderazgo compartido— se corrige en un lugar y se propaga a todos.

github.com/juandiazr513/matricula-2025
"""

from pathlib import Path
import numpy as np
import pandas as pd

# ── constantes de la base ──────────────────────────────────────────────────────
MATRICULA_OFICIAL = 1_455_639          # informe SIES "Matrícula en Educación Superior 2025"
FILAS_ESPERADAS   = 16_089
UNAB              = 'UNIVERSIDAD ANDRES BELLO'

COLS_EDAD = ['e15_19', 'e20_24', 'e25_29', 'e30_34', 'e35_39', 'e40_mas', 'e_sin_info']
COLS_TES  = ['tes_mun', 'tes_psub', 'tes_ppag', 'tes_cad', 'tes_slep']

# Paleta del sitio. El color codifica una sola cosa: la relación con la institución en foco.
PALETA = {
    'foco':   '#1f3fa8',
    'lider':  '#a9550b',
    'gris':   '#b9bfc7',
    'gris2':  '#cbd0d7',
    'tinta':  '#10141a',
    'suave':  '#69727e',
    'linea':  '#d6dae0',
}

ESTILO = {
    'figure.dpi': 110, 'font.size': 9,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'grid.alpha': .25, 'grid.linewidth': .6, 'axes.axisbelow': True,
    'legend.frameon': False,
}


def cargar_base(ruta=None):
    """Lee la base limpia. Funciona desde la raíz del repo o desde notebooks/."""
    if ruta is None:
        candidatos = [Path('data/matricula2025.csv'), Path('../data/matricula2025.csv')]
        ruta = next((p for p in candidatos if p.exists()), None)
        if ruta is None:
            raise FileNotFoundError(
                'No se encontró data/matricula2025.csv. Corre esto desde el repo.')
    return pd.read_csv(ruta)


AMBITOS = {
    'Pregrado':     lambda d: d.nivel_global == 'Pregrado',
    'Posgrado':     lambda d: d.nivel_carrera.isin(['Magister', 'Doctorado']),
    'Especialidad': lambda d: d.nivel_carrera == 'Especialidad Médica U Odontológica',
}
# Fuera de alcance por decisión: Diplomado (61.228 alumnos) y Postítulo genérico (3.810).


def construir_mercados(df, foco=UNAB, metrica='mat1_total', ambito='region',
                       universo='__all', nivel='Pregrado',
                       match_jornada=True, match_modalidad=False, match_titulo=True, umbral=5):
    """
    Arma los mercados donde `foco` compite y calcula posición y participación.

    Un mercado es área genérica + territorio, y opcionalmente jornada y modalidad. El área
    genérica del SIES (284 categorías) es la que agrupa programas equivalentes entre
    instituciones; el nombre de carrera no sirve porque hay 5.608 variantes.

    Parámetros que cambian la lectura, no el dato:
      ambito : 'comuna' | 'provincia' | 'region' | 'pais'
          El denominador. La misma carrera da 54,7% de participación medida por comuna y 8,9%
          medida por región. Ambas son correctas y responden preguntas distintas.
      match_titulo : bool
          Exige que las carreras del mercado entreguen el mismo tipo de título. Es lo que separa
          bien a los IP de las universidades, y mejor que filtrar por tipo de institución: los IP
          no pueden entregar licenciatura (0 alumnos en toda la base), así que entran solo donde
          compiten de verdad. Apagarlo mete en el mismo mercado una licenciatura y un técnico de
          nivel superior, que no son el mismo producto.
      umbral : float
          Brecha máxima, en % del máximo del mercado, para considerar el liderazgo compartido.
          Con 0 solo entran los empates exactos. Es una convención de materialidad declarada,
          no una prueba estadística: la base es censal y no tiene error muestral.

    Devuelve una fila por institución y mercado, solo en los mercados donde `foco` está presente.
    """
    d = df.copy()
    if universo != '__all':
        d = d[d.tipo_inst == universo]
    if nivel in AMBITOS:
        d = d[AMBITOS[nivel](d)]
    elif nivel != '__all':
        d = d[d.nivel_global == nivel]

    # Con primer año, una carrera sin admitidos no compite por el estudiante de este año.
    d = d[d[metrica].notna() & (d[metrica] > 0)]

    d['geo'] = 'PAÍS' if ambito == 'pais' else d[ambito]
    llave = ['area_generica', 'geo']
    if match_jornada:
        llave.append('jornada')
    if match_modalidad:
        llave.append('modalidad')
    if match_titulo:
        llave.append('nivel_carrera')

    inst = (d.groupby(llave + ['institucion'], observed=True)[metrica].sum()
              .reset_index().rename(columns={metrica: 'val'}))

    g = inst.groupby(llave, observed=True)
    inst['total_mercado'] = g.val.transform('sum')
    inst['max_mercado']   = g.val.transform('max')
    inst['n_inst']        = g.institucion.transform('nunique')
    inst['share']         = inst.val / inst.total_mercado * 100

    # Desempate alfabético explícito. Sin él, el orden de dos instituciones empatadas dependía
    # del orden de las filas del CSV y pandas y JavaScript coronaban a instituciones distintas.
    inst = inst.sort_values(llave + ['val', 'institucion'], ascending=[True]*len(llave)+[False, True])
    inst['pos'] = inst.groupby(llave, observed=True).cumcount() + 1

    # Liderazgo: no es "ser el primero", es "estar a menos del umbral del máximo".
    inst['co_lider']    = inst.val >= inst.max_mercado * (1 - umbral / 100)
    inst['n_colideres'] = inst.groupby(llave, observed=True).co_lider.transform('sum')
    inst['compartido']  = inst.n_colideres > 1

    presentes = inst.loc[inst.institucion == foco, llave].drop_duplicates()
    inst = inst.merge(presentes, on=llave, how='inner')

    # Metadatos del mercado, para poder capitular sin rehacer el cálculo.
    meta = (d.groupby(llave, observed=True)
              .agg(area=('area', 'first'), cine_area=('cine_area', 'first'),
                   cine_subarea=('cine_subarea', 'first'))
              .reset_index())
    inst = inst.merge(meta, on=llave, how='left')

    return inst.sort_values(llave + ['pos'])


def situacion(mk, foco=UNAB):
    """Clasifica cada mercado del foco en las cuatro situaciones que importan."""
    f = mk[mk.institucion == foco].copy()
    f['situacion'] = np.select(
        [f.n_inst == 1,
         f.co_lider & ~f.compartido,
         f.co_lider & f.compartido],
        ['Sin competencia', 'Lidera sola', 'Liderazgo compartido'],
        default='No lidera')
    return f


def resumen_foco(mk, foco=UNAB):
    """Conteo por situación. Es el que reemplazó al viejo 'lidera en N mercados'."""
    f = situacion(mk, foco)
    orden = ['Lidera sola', 'Liderazgo compartido', 'Sin competencia', 'No lidera']
    t = (f.situacion.value_counts().reindex(orden, fill_value=0)
           .rename_axis('situación').to_frame('mercados'))
    t['%'] = (t.mercados / len(f) * 100).round(1)
    return t


def suite(df, foco=UNAB, verbose=True):
    """Chequeos de integridad de la base y de coincidencia con app.js."""
    r = []
    ok = lambda n, c: r.append((n, bool(c)))

    ok(f'filas = {FILAS_ESPERADAS:,}',        len(df) == FILAS_ESPERADAS)
    ok('matrícula = informe SIES',            df.mat_total.sum() == MATRICULA_OFICIAL)
    ok('cod_carrera única',                   df.cod_carrera.is_unique)
    ok('sexo suma al total',
       (df.mat_muj + df.mat_hom + df.mat_nb - df.mat_total).abs().sum() == 0)
    ok('edad suma al total',
       (df[COLS_EDAD].sum(axis=1) - df.mat_total).abs().sum() == 0)
    ok('primer año ≤ total',                  (df.mat1_total > df.mat_total).sum() == 0)
    ok('sin ceros explícitos en primer año',  (df.mat1_total == 0).sum() == 0)
    ok('continuidad no reporta primer año',
       df[df.tipo_plan == 'Plan Regular de Continuidad'].reporta_mat1.sum() == 0)

    ok('IP no entregan licenciatura',
       df[(df.tipo_inst == 'Institutos Profesionales') &
          (df.nivel_carrera == 'Profesional Con Licenciatura')].mat_total.sum() == 0)
    ok('especialidades solo en universidades',
       df[AMBITOS['Especialidad'](df)].tipo_inst.nunique() == 1)

    mk = construir_mercados(df, foco=foco, umbral=5)
    ok('shares suman 100% en cada mercado',
       np.allclose(mk.groupby([c for c in mk.columns if c in
                   ('area_generica', 'geo', 'jornada', 'nivel_carrera')],
                   observed=True).share.sum(), 100))

    t = pd.DataFrame(r, columns=['chequeo', 'pasa'])
    if verbose:
        print(t.to_string(index=False))
        print()
        print('✓ TODO PASA' if t.pasa.all() else '✗ HAY FALLAS')
    return t


# ══════════════════════════════════════════════════════════════════════════════
# SERIE HISTÓRICA 2015-2025
# ══════════════════════════════════════════════════════════════════════════════

def cargar_serie(ruta=None):
    """Lee la serie agregada que produce etl/prep_serie.py."""
    if ruta is None:
        candidatos = [Path('data/serie_2015_2025.csv'), Path('../data/serie_2015_2025.csv')]
        ruta = next((p for p in candidatos if p.exists()), None)
        if ruta is None:
            raise FileNotFoundError('No se encontró data/serie_2015_2025.csv. Corre etl/prep_serie.py.')
    return pd.read_csv(ruta)


def serie_por(s, corte, metrica='mat_total', institucion=None, **filtros):
    """
    Serie anual desglosada por una variable.

    corte : 'modalidad' | 'jornada' | 'tipo_plan' | 'cine_area' | 'area' | 'region' |
            'nivel_global' | 'tipo_inst' | 'institucion'
    filtros : cualquier columna = valor o lista de valores. Ej: nivel_global='Pregrado'
    """
    d = s
    if institucion is not None:
        d = d[d.institucion == institucion]
    for k, v in filtros.items():
        d = d[d[k].isin(v if isinstance(v, (list, tuple, set)) else [v])]
    return d.pivot_table(index='anio', columns=corte, values=metrica, aggfunc='sum', fill_value=0)


def indexar(t, base=None):
    """Convierte a índice base 100 en el primer año (o en `base`)."""
    b = t.loc[base if base is not None else t.index.min()]
    return (t / b.replace(0, np.nan) * 100).round(1)


def shift_share(s, foco=UNAB, anio0=2019, anio1=2025, metrica='mat_total',
                universo='Universidades', nivel='Pregrado',
                llave=('area_generica', 'region', 'jornada')):
    """
    Descompone el cambio de matrícula del foco entre dos años.

    Crecer con el mercado no es lo mismo que ganarle al mercado. Esta función separa las dos cosas:

        Δ = efecto mercado + efecto participación + interacción + entradas − salidas

      efecto mercado       : cuánto habría cambiado el foco si su participación se hubiera
                             mantenido y solo hubiera crecido el mercado.
      efecto participación : cuánto habría cambiado si el mercado se hubiera mantenido y solo
                             hubiera cambiado su participación.
      interacción          : el término cruzado. Se reporta aparte en vez de repartirlo, porque
                             repartirlo es una convención más que hay que declarar.
      entradas / salidas   : mercados donde el foco no estaba en anio0 o ya no está en anio1.
                             No tienen participación previa ni posterior, así que no admiten
                             descomposición y se cuentan enteros.

    ADVERTENCIA: entre 2015 y 2025 el sistema pasó de 156 a 122 instituciones. Si un competidor
    cierra, la participación del foco sube sin que el foco haga nada. Ese movimiento aparece acá
    como "efecto participación" y no se distingue de una ganancia real. Para separarlo hay que
    mirar la entrada y salida de instituciones por mercado.
    """
    llave = list(llave)
    d = s[s[metrica].notna() & (s[metrica] > 0)]
    if universo != '__all':
        d = d[d.tipo_inst == universo]
    if nivel != '__all':
        d = d[d.nivel_global == nivel]
    d = d[d.anio.isin([anio0, anio1])]

    mercado = d.groupby(['anio'] + llave, observed=True)[metrica].sum().rename('M')
    propio  = (d[d.institucion == foco].groupby(['anio'] + llave, observed=True)[metrica]
                 .sum().rename('V'))

    t = pd.concat([mercado, propio], axis=1).reset_index()
    piv = t.pivot_table(index=llave, columns='anio', values=['M', 'V'], observed=True)
    piv.columns = [f'{a}{b}' for a, b in piv.columns]
    piv = piv.rename(columns={f'M{anio0}': 'M0', f'M{anio1}': 'M1',
                              f'V{anio0}': 'V0', f'V{anio1}': 'V1'})
    for c in ['M0', 'M1', 'V0', 'V1']:
        if c not in piv:
            piv[c] = 0
    piv = piv.fillna(0)

    presente0 = piv.V0 > 0
    presente1 = piv.V1 > 0
    ambos = presente0 & presente1

    a = piv[ambos].copy()
    a['S0'] = a.V0 / a.M0
    a['S1'] = a.V1 / a.M1
    a['ef_mercado']  = a.S0 * (a.M1 - a.M0)
    a['ef_share']    = a.M0 * (a.S1 - a.S0)
    a['interaccion'] = (a.M1 - a.M0) * (a.S1 - a.S0)

    entradas = piv[~presente0 & presente1].V1.sum()
    salidas  = piv[presente0 & ~presente1].V0.sum()

    desc = pd.Series({
        'efecto mercado':       a.ef_mercado.sum(),
        'efecto participación': a.ef_share.sum(),
        'interacción':          a.interaccion.sum(),
        'entradas a mercados nuevos': entradas,
        'salidas de mercados':  -salidas,
    }).round(0)

    total_real = piv.V1.sum() - piv.V0.sum()
    assert abs(desc.sum() - total_real) < 1, f'La descomposición no cuadra: {desc.sum()} vs {total_real}'

    return {
        'descomposicion': desc,
        'V0': int(piv.V0.sum()), 'V1': int(piv.V1.sum()),
        'delta': int(total_real),
        'mercados_comunes': int(ambos.sum()),
        'mercados_nuevos': int((~presente0 & presente1).sum()),
        'mercados_abandonados': int((presente0 & ~presente1).sum()),
        'detalle': a,
    }


def instituciones_por_anio(s):
    """Cuántas instituciones hay cada año y cuáles entran o salen. El denominador se mueve."""
    r = []
    anios = sorted(s.anio.unique())
    prev = None
    for a in anios:
        act = set(s[s.anio == a].institucion.unique())
        r.append({
            'anio': a,
            'instituciones': len(act),
            'entran': len(act - prev) if prev else None,
            'salen': len(prev - act) if prev else None,
            'salieron': ', '.join(sorted(prev - act)[:3]) if prev and (prev - act) else '',
        })
        prev = act
    return pd.DataFrame(r)
