"""
Acreditación institucional — CNA.

FUENTE
    Buscador Avanzado de Procesos de Acreditación Institucional de la CNA, exportado como
    "Resultado_Buscador_Avanzado_Procesos_Acreditación_Institucional.xls". Pese a la extensión,
    el archivo es XML de Excel 2003 (SpreadsheetML), no un .xls binario: pandas.read_excel no lo
    abre y hay que parsearlo como XML.

QUÉ APORTA QUE NO TENGA LA BASE DE MATRÍCULA
    El SIES solo trae `acred_inst` con tres valores: ACREDITADA, NO ACREDITADA, BAJO TUTELA.
    No trae nivel, ni años, ni vigencia. Todo eso viene de acá.

LOS NIVELES DE LA LEY 21.091
    De Excelencia : 6 o 7 años
    Avanzado      : 4 o 5 años
    Básico        : 3 años

    Los 2 años SÍ existen en el archivo, pero solo en decisiones del régimen anterior (Ley 20.129),
    que no usaba niveles: ARCIS, U. del Mar, UNICIT, INACAP, CFT Proandes y CFT Insec. Las seis
    terminaron NO ACREDITADAS. Hay incluso una reposición de 1 año. Bajo el marco vigente el
    mínimo es 3 y no hay ningún proceso de 2.

DÓNDE VIVE EL DATO
    Las columnas Años/Desde/Hasta de arriba solo vienen llenas cuando el proceso está cerrado.
    En los 13 procesos "ACREDITADA (EN PROCESO)" están vacías y el dato está en las etapas
    Decisión, Reposición y Apelación. La Universidad Adventista, la Del Alba y la de Aysén son
    de ese tipo: aparecen como BÁSICO sin años, pero tienen 3 años vigentes hasta 2026.

    Regla de resolución: gana la última etapa que ACOGE; si ninguna acoge, manda la Decisión.
    Años = 0 no es una duración: es el marcador de un NO ACOGE.

EL CRUCE CON EL SIES
    Los nombres no calzan: el SIES abrevia el tipo de institución ("CFT ALPES") y la CNA lo
    escribe completo ("CENTRO DE FORMACIÓN TÉCNICA ALPES"). La normalización de acá resuelve la
    mayoría; el resto va en EQUIVALENCIAS, que es una tabla manual y hay que mantenerla.
"""

import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

NS = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}

CANDIDATOS = [
    Path('data/raw/Resultado_Buscador_Avanzado_Procesos_Acreditación_Institucional.xls'),
    Path('../data/raw/Resultado_Buscador_Avanzado_Procesos_Acreditación_Institucional.xls'),
    Path('data/acreditacion_cna.csv'),
    Path('../data/acreditacion_cna.csv'),
]

# Niveles y su rango legal de años. Se usa para validar que el archivo no traiga combinaciones
# imposibles, no para imputar nada.
NIVELES = {
    'DE EXCELENCIA': (6, 7),
    'AVANZADO':      (4, 5),
    'BÁSICO':        (3, 3),
}

ORDEN_NIVEL = ['DE EXCELENCIA', 'AVANZADO', 'BÁSICO', 'NO ACREDITADA']

# Pares que la normalización automática no resuelve. Cada línea es una decisión manual:
# clave normalizada del SIES -> clave normalizada de la CNA.
EQUIVALENCIAS = {
    'IP IACC': 'IP INSTITUTO PROFESIONAL IACC',
    'IP IPG': 'IP IPG INSTITUTO PROFESIONAL',
    'CFT PUCV': 'CFT PONTIFICIA U CATOLICA VALPARAISO',
    'U CATOLICA CARDENAL RAUL SILVA HENRIQUEZ': 'U CATOLICA SILVA HENRIQUEZ',
    'IP DR VIRGINIO GOMEZ G': 'IP VIRGINIO GOMEZ',
}


def normalizar(s):
    """Lleva un nombre de institución a una clave comparable entre el SIES y la CNA."""
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().upper()
    s = re.sub(r'[^A-Z0-9 ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'^CENTRO DE FORMACION TECNICA\b', 'CFT', s)
    s = re.sub(r'^INSTITUTO PROFESIONAL\b', 'IP', s)
    s = re.sub(r'^PONTIFICIA UNIVERSIDAD\b', 'U', s)
    s = re.sub(r'^UNIVERSIDAD\b', 'U', s)
    s = re.sub(r'^(CFT|IP|U) (DE LA|DEL|DE|LA)\b', r'\1', s)
    return re.sub(r'\s+', ' ', s).strip()


def leer_cna(ruta=None):
    """Parsea el XML de la CNA y devuelve un proceso por fila."""
    if ruta is None:
        ruta = next((p for p in CANDIDATOS if p.exists()), None)
        if ruta is None:
            raise FileNotFoundError(
                'No se encontró el archivo de la CNA. Déjalo en data/raw/ o genera '
                'data/acreditacion_cna.csv con etl/prep_acreditacion.py.')
    ruta = Path(ruta)
    if ruta.suffix == '.csv':
        return pd.read_csv(ruta)

    hoja = ET.parse(ruta).getroot().find('.//ss:Worksheet', NS)
    filas = []
    for r in hoja.findall('.//ss:Row', NS):
        fila = []
        for c in r.findall('ss:Cell', NS):
            dato = c.find('ss:Data', NS)
            fila.append(dato.text if dato is not None else '')
        filas.append(fila)

    head = filas[0]
    d = pd.DataFrame([f for f in filas[1:] if len(f) == len(head)], columns=head)

    # Hay dos columnas llamadas "Vinculación con el Medio" (criterios de dos marcos distintos).
    d = d.loc[:, ~d.columns.duplicated()]

    d = d.rename(columns={
        'Id Proceso CNA': 'id_proceso', 'Tipo Institución': 'tipo_cna', 'Institución': 'institucion_cna',
        'Resultado': 'resultado', 'Nivel': 'nivel', 'Años': 'anios',
        'Desde': 'desde', 'Hasta *': 'hasta', 'Agencia': 'agencia',
    })
    d['resultado_raw'] = d.resultado
    d['resultado'] = d.resultado.str.replace(r'<br/>.*', '', regex=True).str.strip()
    d['en_proceso'] = d.resultado_raw.str.contains('EN PROCESO', na=False)
    d['anios'] = pd.to_numeric(d.anios, errors='coerce')
    d['desde'] = pd.to_datetime(d.desde, format='%d/%m/%Y', errors='coerce')
    d['hasta'] = pd.to_datetime(d.hasta, format='%d/%m/%Y', errors='coerce')

    d = _rescatar_de_etapas(d)

    d['anios'] = d.anios.astype('Int64')
    d['anio_acreditacion'] = d.desde.dt.year.astype('Int64')
    d['k'] = d.institucion_cna.map(normalizar)

    # El marco de niveles es de la Ley 21.091. Los procesos sin nivel y con 2 o menos años son
    # del régimen anterior y no admiten lectura por nivel.
    d['marco'] = 'Ley 21.091'
    d.loc[d.nivel.isna() & (d.anios <= 2), 'marco'] = 'Ley 20.129 (régimen anterior)'

    d = _derivar_nivel(d)
    return d


def _derivar_nivel(d):
    """
    Asigna nivel por tramo de años cuando la CNA no lo puso.

    La CNA solo asigna nivel en los procesos de la Ley 21.091. Los anteriores traen años pero no
    nivel, y quedarían fuera de cualquier corte por nivel sin avisar. El caso que obliga a esto es
    la Pontificia Universidad Católica: acreditada por 7 años bajo el marco antiguo, segunda
    universidad del país con 55.730 alumnos, y sin nivel asignado.

    La regla usa los mismos tramos que la ley (6-7 De Excelencia, 4-5 Avanzado, 3 Básico), y solo
    aplica a instituciones ACREDITADAS: un proceso de 2 años que terminó no acreditado no tiene
    nivel equivalente, tiene un rechazo.

    `nivel_derivado` marca estos casos. En un informe corresponde decir "nivel equivalente según
    tramo de años", no "nivel De Excelencia": la CNA no lo declaró así.
    """
    def tramo(a):
        if pd.isna(a):
            return None
        if a >= 6:
            return 'DE EXCELENCIA'
        if a >= 4:
            return 'AVANZADO'
        if a == 3:
            return 'BÁSICO'
        return None                      # 1 y 2 años: régimen anterior, sin equivalencia

    falta = d.nivel.isna() & d.resultado.eq('ACREDITADA') & d.anios.notna()
    d['nivel_derivado'] = False
    d.loc[falta, 'nivel'] = d.loc[falta, 'anios'].map(tramo)
    d.loc[falta & d.nivel.notna(), 'nivel_derivado'] = True
    return d


ETAPAS = ['Apelación', 'Reposición', 'Decisión']


def _rescatar_de_etapas(d):
    """
    Rellena años y vigencia desde las etapas cuando las columnas de arriba vienen vacías.

    Ocurre en los 13 procesos "ACREDITADA (EN PROCESO)". Gana la última etapa que ACOGE; si
    ninguna acoge, manda la Decisión. Un Años = 0 se descarta: marca un NO ACOGE, no una duración.
    """
    d['rescatado'] = False
    for et in ETAPAS:
        col_a = f'{et}/Años'
        col_d = f'{et}/Fecha Vigencia Desde'
        col_h = f'{et}/Fecha Vigencia Hasta'
        if col_a not in d:
            continue
        a = pd.to_numeric(d[col_a], errors='coerce').replace(0, float('nan'))
        res = d.get(f'{et}/Resultado', d.get(f'{et}/Resultado Acreditacíón'))
        # Apelación y Reposición solo mandan si acogen. La Decisión siempre es válida.
        valida = a.notna() if et == 'Decisión' else (a.notna() & res.eq('ACOGE'))
        falta = d.anios.isna() & valida
        if falta.any():
            d.loc[falta, 'anios'] = a[falta].to_numpy()
            d.loc[falta, 'desde'] = pd.to_datetime(d.loc[falta, col_d], format='%d/%m/%Y', errors='coerce').to_numpy()
            d.loc[falta, 'hasta'] = pd.to_datetime(d.loc[falta, col_h], format='%d/%m/%Y', errors='coerce').to_numpy()
            d.loc[falta, 'rescatado'] = True
    return d


def vigente(cna, fecha=None):
    """
    Un proceso por institución: el vigente a la fecha, o el más reciente si ninguno lo está.

    Cuatro instituciones tienen más de un proceso en el archivo. Quedarse con cualquiera sería
    arbitrario, así que se prioriza el que cubre la fecha de corte.
    """
    fecha = pd.Timestamp(fecha or 'today')
    d = cna.copy()
    d['cubre'] = (d.desde <= fecha) & (d.hasta >= fecha)
    d = d.sort_values(['k', 'cubre', 'desde'], ascending=[True, False, False])
    return d.groupby('k', as_index=False).first()


def unir(matricula, cna=None, fecha=None):
    """
    Pega la acreditación a la base de matrícula.

    Devuelve (df_con_acreditacion, no_cruzadas). Revisa siempre `no_cruzadas`: lo que no cruza
    queda con acreditación nula y desaparece de cualquier corte por nivel, sin avisar.
    """
    cna = vigente(cna if cna is not None else leer_cna(), fecha)
    d = matricula.copy()
    d['k'] = d.institucion.map(normalizar).replace(EQUIVALENCIAS)

    cols = ['k', 'institucion_cna', 'resultado', 'nivel', 'anios', 'desde', 'hasta',
            'anio_acreditacion', 'agencia', 'marco', 'nivel_derivado', 'rescatado']
    d = d.merge(cna[cols], on='k', how='left')

    # Nivel operativo: los no acreditados no tienen nivel en el archivo, pero sí son una categoría.
    d['nivel_acred'] = d.nivel.fillna(
        d.resultado.map({'NO ACREDITADA': 'NO ACREDITADA'}))
    d['tramo_anios'] = pd.cut(d.anios.astype('float'), [2.5, 3.5, 5.5, 7.5],
                              labels=['3 años', '4–5 años', '6–7 años'])

    faltan = (d[d.resultado.isna()]
                .groupby('institucion', as_index=False)
                .agg(matricula=('mat_total', 'sum'), tipo=('tipo_inst', 'first'))
                .sort_values('matricula', ascending=False))
    return d, faltan


def validar(cna):
    """Chequea que los niveles y los años del archivo sean consistentes con la Ley 21.091."""
    r = []
    ok = lambda n, c: r.append((n, bool(c)))

    acred = cna[cna.resultado == 'ACREDITADA']
    for niv, (lo, hi) in NIVELES.items():
        x = acred[acred.nivel == niv].anios.dropna()
        ok(f'{niv}: años entre {lo} y {hi}', x.between(lo, hi).all() if len(x) else True)

    ok('sin acreditaciones de 2 años bajo la Ley 21.091',
       (cna[cna.marco == 'Ley 21.091'].anios <= 2).sum() == 0)
    ok('los 2 años del régimen anterior terminaron no acreditados',
       cna[cna.marco != 'Ley 21.091'].resultado.eq('NO ACREDITADA').all())
    ok('Adventista, Del Alba y Aysén tienen 3 años rescatados',
       cna[cna.institucion_cna.str.contains('ADVENTISTA|DEL ALBA|AYSÉN', na=False)].anios.eq(3).all())
    ok('los sin nivel son los no acreditados o del régimen anterior',
       cna[cna.nivel.isna()].resultado.eq('NO ACREDITADA').all())
    ok('la PUC queda De Excelencia por sus 7 años',
       cna.loc[cna.institucion_cna.str.contains('CATÓLICA DE CHILE', na=False), 'nivel']
          .eq('DE EXCELENCIA').all())
    ok('ninguna institución no acreditada recibió nivel derivado',
       not (cna.nivel_derivado & cna.resultado.ne('ACREDITADA')).any())
    ok('un proceso por institución tras vigente()', vigente(cna).k.is_unique)

    t = pd.DataFrame(r, columns=['chequeo', 'pasa'])
    print(t.to_string(index=False))
    print()
    print('✓ TODO PASA' if t.pasa.all() else '✗ HAY FALLAS')
    return t
