# Competencia por carrera — Matrícula SIES 2025

Sitio estático para analizar la matrícula de educación superior chilena a nivel de mercado local:
para cada carrera de una institución, quiénes más la dictan en el mismo territorio y jornada, y
qué participación tiene cada una.

**Fuente:** Servicio de Información de Educación Superior (SIES), Mineduc.
Base de matrícula 2025, corte 15-07-2025. 16.089 carreras · 121 instituciones · 1.455.639 matriculados.

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
index.html                 vista Competencia por carrera
assets/app.css             estilos
assets/app.js              carga, cálculo de mercados y render
data/matricula2025.csv     base limpia (7,5 MB → 775 KB gzip en el navegador)
etl/prep.py                script que genera la base limpia desde el CSV original del SIES
```

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

Los cálculos en JavaScript están verificados contra los mismos agregados hechos en pandas
(mismo número de mercados, mismas participaciones, mismos liderazgos).

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
