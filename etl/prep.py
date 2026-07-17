import pandas as pd, numpy as np, json, os

SRC = '/mnt/user-data/uploads/Matricula_2025_WEB_15_07_2025.csv'
df = pd.read_csv(SRC, sep=';', encoding='latin-1', low_memory=False)
df.columns = [c.strip() for c in df.columns]

REN = {
 'TOTAL MATRÍCULA':'mat_total','TOTAL MATRÍCULA MUJERES':'mat_muj','TOTAL MATRÍCULA HOMBRES':'mat_hom',
 'TOTAL MATRÍCULA NO BINARIOS O INDEFINIDOS':'mat_nb','TOTAL MATRÍCULA PRIMER AÑO':'mat1_total',
 'TOTAL MATRÍCULA MUJERES PRIMER AÑO':'mat1_muj','TOTAL MATRÍCULA HOMBRES PRIMER AÑO':'mat1_hom',
 'TOTAL MATRÍCULA NO BINARIOS O INDEFINIDOS PRIMER AÑO':'mat1_nb',
 'CLASIFICACIÓN INSTITUCIÓN NIVEL 1':'tipo_inst','CLASIFICACIÓN INSTITUCIÓN NIVEL 2':'inst_n2',
 'CLASIFICACIÓN INSTITUCIÓN NIVEL 3':'inst_n3','CÓDIGO DE INSTITUCIÓN':'cod_inst',
 'NOMBRE INSTITUCIÓN':'institucion','ACREDITACIÓN INSTITUCIONAL':'acred_inst',
 'REGIÓN':'region','PROVINCIA':'provincia','COMUNA':'comuna','NOMBRE SEDE':'sede',
 'NOMBRE CARRERA':'carrera','ÁREA DEL CONOCIMIENTO':'area','ÁREA CARRERA GENÉRICA':'area_generica',
 'CINE-F 2013 ÁREA':'cine_area','CINE-F 2013 SUBAREA':'cine_subarea',
 'NIVEL GLOBAL':'nivel_global','CARRERA CLASIFICACIÓN NIVEL 1':'nivel_carrera',
 'CARRERA CLASIFICACIÓN NIVEL 2':'nivel_carrera2','MODALIDAD':'modalidad','JORNADA':'jornada',
 'TIPO DE PLAN DE LA CARRERA':'tipo_plan','DURACIÓN TOTAL DE CARRERA':'duracion',
 'CÓDIGO CARRERA':'cod_carrera','ACREDITACIÓN CARRERA':'acred_carrera',
 'RANGO DE EDAD 15 A 19 AÑOS':'e15_19','RANGO DE EDAD 20 A 24 AÑOS':'e20_24','RANGO DE EDAD 25 A 29 AÑOS':'e25_29',
 'RANGO DE EDAD 30 A 34 AÑOS':'e30_34','RANGO DE EDAD 35 A 39 AÑOS':'e35_39','RANGO DE EDAD 40 Y MÁS AÑOS':'e40_mas',
 'PROMEDIO EDAD CARRERA':'edad_prom','RANGO DE EDAD SIN INFORMACIÓN':'e_sin_info',
 'TES MUNICIPAL':'tes_mun','TES PARTICULAR SUBVENCIONADO':'tes_psub','TES PARTICULAR PAGADO':'tes_ppag',
 'TES CORP. DE ADMINISTRACIÓN DELEGADA':'tes_cad','TES SERVICIO LOCAL EDUCACION':'tes_slep',
 'TOTAL TES':'tes_total','% COBERTURA TES':'tes_cob',
}
d = df[list(REN)].rename(columns=REN)

# decimales con coma -> float
for c in ['edad_prom']:
    d[c] = pd.to_numeric(d[c].astype(str).str.replace(',','.'), errors='coerce')
d['tes_cob'] = pd.to_numeric(d['tes_cob'].astype(str).str.replace('%','').str.replace(',','.'), errors='coerce')

# conteos: nulo = cero estructural
COUNTS = ['mat_total','mat_muj','mat_hom','mat_nb',
          'e15_19','e20_24','e25_29','e30_34','e35_39','e40_mas','e_sin_info',
          'tes_mun','tes_psub','tes_ppag','tes_cad','tes_slep','tes_total']
d[COUNTS] = d[COUNTS].fillna(0).astype('int32')

# Primer año NO se rellena con cero. El SIES no escribe ningún cero explícito en esta
# columna (0 ceros, 5.364 vacíos), y los 821 Planes de Continuidad vienen 100% vacíos
# pese a tener 65.693 matriculados: ahí el vacío es "no reporta", no "no admitió".
# Se deja nulo y cada consumidor decide.
MAT1 = ['mat1_total','mat1_muj','mat1_hom','mat1_nb']
d[MAT1] = d[MAT1].astype('Int32')
d['reporta_mat1'] = d.mat1_total.notna()

# limpieza de texto
for c in d.select_dtypes(include='object').columns:
    d[c] = d[c].astype(str).str.strip()

# validación de integridad
chk = {
 'filas': len(d),
 'suma_mat_total': int(d.mat_total.sum()),
 'sexo_cuadra': int((d.mat_muj + d.mat_hom + d.mat_nb - d.mat_total).abs().sum()),
 'edad_cuadra': int((d[['e15_19','e20_24','e25_29','e30_34','e35_39','e40_mas','e_sin_info']].sum(1) - d.mat_total).abs().sum()),
 'mat1_gt_total': int((d.mat1_total > d.mat_total).sum()),
 'mat1_ceros_explicitos': int((d.mat1_total == 0).sum()),
 'continuidad_sin_mat1': int(((d.tipo_plan=='Plan Regular de Continuidad') & d.mat1_total.isna()).sum()),
 'cod_carrera_unico': bool(d.cod_carrera.is_unique),
}
print(json.dumps(chk, indent=1, ensure_ascii=False))

os.makedirs('out', exist_ok=True)

d.to_csv('out/matricula2025.csv', index=False, encoding='utf-8')
os.system('gzip -9 -kf out/matricula2025.csv')
for f in os.listdir('out'):
    print(f, round(os.path.getsize('out/'+f)/1024), 'KB')
