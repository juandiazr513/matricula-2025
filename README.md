# Competencia por carrera — Matrícula SIES 2025

Sitio estático para analizar la matrícula de educación superior chilena a nivel de mercado local:
para cada carrera de una institución, quiénes más la dictan en el mismo territorio y jornada, y
qué participación tiene cada una.

**Fuente:** Servicio de Información de Educación Superior (SIES), Mineduc.
Base de matrícula 2025, corte 15-07-2025. 16.089 carreras · 122 instituciones · 1.455.639 matriculados.

## Cómo publicarlo

Repositorio: https://github.com/juandiazr513/matricula-2025
Sitio publicado: https://juandiazr513.github.io/matricula-2025/

### Opción A — arrastrando por la web

1. Crear el repo en https://github.com/new con el nombre `matricula-2025`, público, sin README ni .gitignore.
2. En la pantalla siguiente, clic en **uploading an existing file**.
3. Arrastrar todo el contenido de esta carpeta (incluido `.nojekyll`, que Windows oculta:
   pestaña Vista → Elementos ocultos).
4. **Commit changes**.
5. Settings → Pages → Branch `main` / `(root)` → Save.

### Opción B — desde git

```bash
cd "ruta/a/esta/carpeta"
git init -b main
git add .
git commit -m "Competencia por carrera: base SIES 2025 + vista de mercados"
git remote add origin https://github.com/juandiazr513/matricula-2025.git
git push -u origin main
```

Luego Settings → Pages → Branch `main` / `(root)` → Save.

No hay build ni dependencias que instalar. Cada cambio posterior es
`git add . && git commit -m "..." && git push`; Pages republica solo.

El archivo `.nojekyll` evita que GitHub procese la carpeta con Jekyll. Sin él, el sitio
puede publicar en blanco.

## Estructura

```
index.html                 vista Competencia por carrera (corte 2025)
evolucion.html             vista Evolución 2015-2025
assets/app.css             estilos
assets/app.js              competencia: carga, cálculo de mercados y render
assets/evolucion.js        evolución: serie anual y descomposición shift-share
data/matricula2025.csv     corte 2025 a nivel de carrera (7,5 MB → 775 KB gzip)
data/serie_2015_2025.csv   serie agregada 2015-2025 (20,8 MB → 1,1 MB gzip)
etl/prep.py                genera el corte 2025 desde el archivo original del SIES
etl/prep_serie.py          genera la serie 2015-2025 desde el archivo histórico del SIES
etl/inspeccionar_anios.py  detecta cambios de esquema entre archivos anuales
data/raw/                  archivos crudos del SIES (ignorados por git, ver .gitignore)
analisis/mercados.py       motor de análisis compartido por los notebooks
notebooks/                 exploración, validación y panorama competitivo
```

## Notebooks

- **`01_exploracion_validacion.ipynb`** — recorre la base (estructura, integridad,
  distribuciones, perfil) y reproduce en pandas los cálculos que `app.js` hace en JavaScript,
  para comprobar que coinciden.
- **`02_panorama_unab.ipynb`** — dónde compite UNAB, contra quién y con qué resultado, en
  gráficos. Capitulado por CINE-F 2013.
- **`03_evolucion_2015_2025.ipynb`** — qué se movió en once años y de dónde viene el crecimiento
  de UNAB, con descomposición shift-share.

GitHub los renderiza con las salidas incluidas, no hace falta ejecutarlos para leerlos.

El motor de análisis vive en `analisis/mercados.py` y lo importan los dos. Una sola
implementación: cuando un criterio cambia, cambia en un lugar. Los notebooks no contienen copias
de `construir_mercados`.

Para correrlo: `pip install pandas matplotlib jupyter` y abrirlo desde la raíz del repo o desde
`notebooks/` (resuelve la ruta del CSV solo).

La validación no fue decorativa. En su primera corrida destapó tres problemas:

1. UNAB y la U. Diego Portales empatan con 32 matriculados de primer año en Administración de
   Empresas RM vespertino, y el desempate quedaba a merced del orden de las filas del CSV: pandas
   y JavaScript coronaban a instituciones distintas.
2. El "líder" de Ingeniería Comercial RM diurno le gana al segundo por 3 alumnos en un mercado de
   5.265. Se estaba reportando como una ventaja.
3. 15 de los 42 liderazgos originales eran mercados donde UNAB es la única oferente.

Los tres están corregidos: desempate alfabético explícito, umbral de liderazgo compartido, y los
monopolios contados aparte.

## Sobre los datos

`etl/prep.py` toma el archivo original del SIES (`Matricula_2025_WEB_15_07_2025.csv`, ISO-8859-1,
separador `;`, decimales con coma) y produce la base limpia: UTF-8, snake_case, 47 columnas.

Criterios aplicados:

- **Nulos en conteos → cero.** En la base del SIES un vacío significa "no hay matrícula en esa
  categoría", no "dato faltante". Se convierten a cero.
- **Nulos en promedios y porcentajes → se preservan.** Ahí un vacío sí es ausencia de dato y
  rellenarlo con cero corrompería cualquier promedio.
- **Grano:** una fila = una carrera única (`cod_carrera` es llave). No es dato de estudiante.

Validaciones que corre el script en cada ejecución:

| Chequeo | Resultado |
|---|---|
| Suma por sexo = matrícula total | desviación 0 en 16.089 filas |
| Suma de rangos etarios = matrícula total | desviación 0 |
| Matrícula de primer año ≤ matrícula total | 0 violaciones |
| `cod_carrera` único | sí |

## Cómo se define un mercado

Un mercado es la combinación de **área genérica de carrera + territorio**, y opcionalmente jornada
y modalidad. El área genérica (284 categorías del SIES) es la que agrupa programas equivalentes
entre instituciones; el nombre de carrera no sirve para eso porque hay 5.608 variantes de nombre.

El territorio es configurable —comuna, provincia, región o país— porque el resultado depende de
él. Psicología diurna en Las Condes da 54,7% de participación a UNAB; la misma carrera medida a
nivel de Región Metropolitana da 8,9%. La segunda cifra es la relevante: un postulante de Maipú
elige entre todo Santiago, no entre las universidades de su comuna. El default es región.

Cuando la métrica es matrícula de primer año, las carreras con cero matriculados nuevos quedan
fuera del mercado: no compiten por el estudiante de este año.

Los cálculos en JavaScript están verificados contra los mismos agregados hechos en pandas: 128
mercados, mismo desglose de liderazgos, mismas participaciones.
Ver `notebooks/01_exploracion_validacion.ipynb`.

## Liderazgo compartido

Ser el primero de la lista no siempre es liderar. El sitio distingue tres situaciones:

- **Lidera sola**: supera al segundo por más del umbral.
- **Liderazgo compartido**: la brecha con el máximo es menor o igual al umbral (5% por defecto,
  configurable a 0%, 2% o 10%). Se marcan todas las colíderes y la posición se muestra como `1=`.
- **Sin competencia**: es la única oferente del mercado. No se cuenta como liderazgo.

El umbral es una **convención de materialidad, no una prueba estadística**: la base es censal y no
tiene error muestral. Calibrarlo bien exigiría la serie histórica, para saber cuánto se mueve la
cifra de un año a otro. Con 5% la brecha más grande declarada empatada es de 6 alumnos; con 10%
sería de 23, que es demasiado.

Para UNAB en pregrado, con el default: **25 liderazgos limpios, 3 compartidos y 15 mercados sin
competencia**, sobre 128.

## Advertencias de interpretación

- **Cobertura TES** (tipo de establecimiento de origen) solo es válida en primer año de pregrado.
  El sitio la bloquea en los demás niveles.
- **Promedios de edad del mercado** están ponderados por matrícula de cada carrera, no son
  promedios simples entre instituciones.
- **No binarios** tiene dato en 27 de 16.089 filas. No admite desagregación.
- La base es un corte único de 2025. No hay serie temporal.

## Extender el sitio

Toda la base queda en memoria (`ROWS` en `app.js`) y cada control recalcula desde cero. Agregar
una vista nueva no requiere tocar el pipeline de datos: basta agregar una función que agrupe
`ROWS` como necesite.

Vistas pendientes: panorama del sistema, participación por área, y perfil de entrada comparado.


## Los archivos crudos no van al repo

El histórico del SIES (`Matricula_2007_2025_WEB_*.csv`) pesa 139 MB y GitHub rechaza sobre 100 MB.
Tampoco hace falta versionarlo: es el insumo, no el producto. `.gitignore` bloquea `data/raw/`.

Para regenerar las bases desde cero:

1. Baja de mifuturo.cl/sies o datosabiertos.mineduc.cl los archivos `Matricula_2025_WEB_*.csv` y
   `Matricula_2007_2025_WEB_*.csv`.
2. Déjalos en `data/raw/`.
3. `python etl/prep.py` → `data/matricula2025.csv`
4. `python etl/prep_serie.py` → `data/serie_2015_2025.csv`

Ambos scripts validan integridad en cada corrida y fallan si la agregación pierde matrícula.

## La serie histórica

`etl/prep_serie.py` toma el archivo histórico del SIES (`Matricula_2007_2025_WEB_*.csv`, 264.258
filas, 145 MB) y produce `data/serie_2015_2025.csv`: agregado por año, institución, área genérica,
región, jornada, modalidad, tipo de plan y nivel. Las 167.244 filas del período bajan a 102.641 sin
perder un solo alumno, y el archivo queda en 1,1 MB servido con gzip.

La matrícula 2025 de la serie coincide exacto con el corte independiente que usa la otra vista:
1.455.639 en ambos.

**Por qué 2015.** El Plan Regular de Continuidad nace ese año con 26 alumnos; hoy es un quinto del
pregrado online. Además 2015–2019 deja cinco años de línea base pre-pandemia. Cambiar el rango es
una línea: `ANIO_INICIO` en `etl/prep_serie.py`.

**MODALIDAD solo existe desde 2011.** Antes se reconstruye desde `JORNADA`, y la equivalencia está
verificada: en los 15 años donde ambas columnas conviven, la jornada "A Distancia" y la modalidad
"No Presencial" dan cifras idénticas, sin una sola excepción. La categoría semipresencial no se
recupera igual.

## Shift-share

`analisis/mercados.shift_share()` separa cuánto del cambio de una institución vino porque el
mercado creció y cuánto porque ganó participación:

    Δ = efecto mercado + efecto participación + interacción + entradas − salidas

Las entradas y salidas van aparte porque un mercado donde la institución no estaba antes no tiene
participación previa y no admite descomposición. La interacción se reporta separada en vez de
repartirla, porque repartirla es otra convención que habría que declarar.

El cálculo está implementado dos veces —pandas en el módulo, JavaScript en `assets/evolucion.js`—
y ambas coinciden exacto.

**Advertencia que va en la lámina, no en el pie:** el sistema pasó de 156 instituciones en 2015 a
122 en 2025. Si un competidor cierra, la participación de los demás sube sin que hagan nada, y
esta descomposición lo registra como "efecto participación" sin distinguirlo de una ganancia real.
