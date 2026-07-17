"""
Especialidades médicas y odontológicas — construcción de una llave comparable.

EL PROBLEMA
    El SIES clasifica las 577 especialidades bajo una sola área genérica, "Postítulo en Salud".
    Eso deja un único mercado con 21 universidades: inservible para comparar.

    Y los nombres no son comparables entre instituciones. La misma especialidad aparece como
    "MEDICINA INTERNA", "TITULO DE PROFESIONAL ESPECIALISTA EN MEDICINA INTERNA" y "MEDICA EN
    MEDICINA INTERNA". No hay ninguna columna en la base que las una.

LO QUE HACE ESTE MÓDULO
    Extrae el núcleo de cada nombre quitando los prefijos administrativos, y agrupa por ese
    núcleo. Es trabajo mecánico: resuelve la mayoría, no todo.

LO QUE NO HACE
    No decide cuál es el nombre canónico. CONACEM certifica 68 especialidades médicas (31
    primarias y 37 derivadas) y el Decreto Afecto N°8 del MINSAL lista 52, pero ese listado
    oficial no está en la base ni se incorporó acá. La columna `propuesta` de la tabla de salida
    es la forma más frecuente dentro de cada grupo, no un nombre oficial.

    Cualquier cifra por especialidad que salga de esta agrupación es provisional hasta que la
    tabla esté revisada por alguien que conozca la nomenclatura.
"""

import re
import unicodedata

import pandas as pd

# Prefijos administrativos que las universidades anteponen y que no distinguen especialidades.
# El orden importa: los más largos primero, o se comen mal.
PREFIJOS = [
    r'PROGRAMA DE FORMACION DE ESPECIALISTAS? (?:MEDICOS? )?EN',
    r'PROGRAMA DE TITULO DE ESPECIALISTA (?:MEDICO |ODONTOLOGICO )?EN',
    r'PROGRAMA DE ESPECIALIZACION (?:ODONTOLOGICA |MEDICA |PROFESIONAL )?EN',
    r'PROGRAMA DE ESPECIALIDAD (?:ODONTOLOGICA |MEDICA )?EN',
    r'POSTITULO DE ESPECIALIZACION (?:ODONTOLOGICA |MEDICA )?EN',
    r'POSTITULO DE ESPECIALIDAD (?:ODONTOLOGICA |MEDICA )?EN',
    r'TITULO DE PROFESIONAL ESPECIALISTA EN',
    r'TITULO DE ESPECIALISTA (?:MEDICO |ODONTOLOGICO )?EN',
    r'FORMACION DE (?:MEDICO )?ESPECIALISTAS? EN',
    r'FORMACION ESPECIALISTA EN',
    r'ESPECIALIZACION (?:ODONTOLOGICA |ODONTOLOGIA |MEDICA )?EN',
    r'ESPECIALIDAD (?:ODONTOLOGICA |MEDICA )?EN',
    r'ESPECIALISTA (?:MEDICO |ODONTOLOGICO )?EN',
    r'ESPECIALIZACION EN',
    r'POSTITULO EN',
    r'PROGRAMA DE',
    r'ODONTOLOGICA EN',
    r'MEDICA EN',
    r'MEDICO EN',
    # Variantes sin "EN": "POSTITULO DE ESPECIALIDAD MEDICA MEDICINA INTERNA"
    r'POSTITULO DE ESPECIALIDAD (?:ODONTOLOGICA|MEDICA)',
    r'ESPECIALIDAD (?:ODONTOLOGICA|MEDICA)',
    r'ESPECIALIZACION (?:ODONTOLOGICA|MEDICA)',
    r'TITULO DE ESPECIALISTA',
    r'ESPECIALISTA',
    r'POSTITULO',
]

# Palabras que no distinguen especialidades y estorban al comparar el orden de los términos.
# Ojo con lo que NO está acá: ADULTO, INFANTIL, PEDIATRICA sí distinguen y se conservan.
VACIAS = {'DE', 'DEL', 'LA', 'EL', 'LOS', 'LAS', 'Y', 'E', 'EN', 'PARA', 'CON', 'A'}

# Singularización mínima, solo para que ADULTOS y ADULTO caigan juntos.
def _singular(t):
    if len(t) > 4 and t.endswith('ES'):
        return t[:-2]
    if len(t) > 3 and t.endswith('S') and not t.endswith('IS'):
        return t[:-1]
    return t


def firma(n):
    """
    Conjunto ordenado de términos significativos.

    Existe para que "TRAUMATOLOGIA Y ORTOPEDIA" y "ORTOPEDIA Y TRAUMATOLOGIA" caigan en el mismo
    grupo. Es una heurística: dos especialidades distintas con los mismos términos se unirían mal.
    Por eso la tabla de salida conserva todos los nombres originales de cada grupo, para que la
    revisión pueda deshacer lo que esté mal unido.
    """
    ts = [_singular(t) for t in n.split() if t not in VACIAS]
    return ' '.join(sorted(set(ts)))

# Sufijos que marcan una mención dentro de una especialidad, no una especialidad distinta.
# CONACEM llama "Mención" a esa categoría y explícitamente no la considera una especialidad.
SUFIJOS_MENCION = r'\s+(?:MENCION|CON MENCION EN|CON MENCION)\s+.*$'

ODONTO = ['ODONTO', 'DENTAL', 'DENTO', 'BUCAL', 'BUCO', 'ORAL', 'ENDODONCIA', 'PERIODONCIA',
          'ORTODONCIA', 'IMPLANTOLOGIA', 'MAXILOFACIAL', 'PROTESIS', 'CARIOLOGIA',
          'REHABILITACION ORAL', 'PATOLOGIA ORAL', 'IMAGENOLOGIA ORAL']


def _ascii(s):
    return unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().upper()


def nucleo(nombre):
    """Quita los prefijos administrativos y devuelve el núcleo de la especialidad."""
    s = _ascii(nombre)
    s = re.sub(r'[^A-Z0-9 ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()

    cambio = True
    while cambio:                       # se aplican en cadena: "PROGRAMA DE" + "ESPECIALIZACION EN"
        cambio = False
        for p in PREFIJOS:
            nuevo = re.sub(r'^' + p + r'\b', '', s).strip()
            if nuevo != s and nuevo:
                s, cambio = re.sub(r'\s+', ' ', nuevo).strip(), True
                break
    return s


def sin_mencion(n):
    """Separa la mención del núcleo. Devuelve (núcleo_base, mención o '')."""
    m = re.search(SUFIJOS_MENCION, n)
    if not m:
        return n, ''
    return re.sub(SUFIJOS_MENCION, '', n).strip(), m.group(0).strip()


def tipo(n):
    return 'Odontológica' if any(k in n for k in ODONTO) else 'Médica'


def mapear(df):
    """
    Toma la base limpia y devuelve la tabla de mapeo de especialidades, para revisión humana.

    Columnas de salida:
        nombre_original  como viene en el SIES
        nucleo           tras quitar prefijos
        base             tras quitar además la mención
        mencion          la mención, si la había
        propuesta        forma más frecuente dentro del grupo. NO es un nombre oficial.
        tipo             Médica u Odontológica, inferido por palabras clave
        instituciones    cuántas la dictan bajo ese núcleo base
        matricula        alumnos
        revisar          marca los casos que no se pueden resolver mecánicamente
    """
    e = df[df.nivel_carrera == 'Especialidad Médica U Odontológica'].copy()
    e['nucleo'] = e.carrera.map(nucleo)
    e[['base', 'mencion']] = e.nucleo.map(lambda n: pd.Series(sin_mencion(n))).apply(pd.Series)
    e['tipo'] = e.base.map(tipo)
    e['firma'] = e.base.map(firma)

    # La propuesta es la forma más frecuente dentro del grupo, medida por matrícula.
    top = (e.groupby(['firma', 'base'], observed=True).mat_total.sum()
             .reset_index().sort_values('mat_total', ascending=False)
             .groupby('firma').base.first().rename('propuesta'))

    g = (e.groupby('firma', observed=True)
           .agg(instituciones=('institucion', 'nunique'),
                matricula=('mat_total', 'sum'),
                programas=('cod_carrera', 'count'),
                tipo=('tipo', 'first'),
                variantes=('base', lambda x: ' | '.join(sorted(set(x)))))
           .reset_index()
           .merge(top, on='firma'))
    g['base'] = g.propuesta
    g['n_variantes'] = g.variantes.str.count(r'\|') + 1

    # Un núcleo que sigue conteniendo palabras administrativas no quedó bien limpio.
    ruido = r'\b(?:TITULO|PROFESIONAL|ESPECIALISTA|ESPECIALIDAD|ESPECIALIZACION|PROGRAMA|FORMACION|POSTITULO)\b'
    g['revisar'] = ''
    g.loc[g.propuesta.str.contains(ruido, na=False, regex=True), 'revisar'] = 'quedan palabras administrativas'
    uno = (g.instituciones == 1) & (g.revisar == '')
    g.loc[uno, 'revisar'] = 'una sola institución: puede ser un duplicado sin unir'
    g.loc[g.propuesta.str.len() < 5, 'revisar'] = 'núcleo demasiado corto'
    g.loc[(g.n_variantes > 1) & (g.revisar == ''), 'revisar'] = 'unió varias formas: confirmar que sean la misma'

    cols = ['propuesta', 'tipo', 'instituciones', 'programas', 'matricula',
            'n_variantes', 'variantes', 'revisar', 'firma']
    return (g[cols].sort_values(['tipo', 'matricula'], ascending=[True, False])
                   .reset_index(drop=True), e)
