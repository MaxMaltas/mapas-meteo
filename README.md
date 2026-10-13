# Automatización diaria de METEO

El proyecto separa la obtención y tratamiento de datos de la edición en After Effects:

1. `scripts/generate_daily.py` consulta AEMET y crea `data/generated/latest/meteo.json`,
   `data/generated/latest/temperaturas_maximas.png` (Península y Baleares) y
   `data/generated/latest/temperaturas_maximas_canarias.png`. También crea
   `data/generated/latest/alertas.png` a partir de los avisos CAP y del mapa
   vectorial `MAPA_ALERTAS_ILUSTRATOR.ai`.
2. `tools/apply_daily_data.jsx` se ejecuta desde After Effects y actualiza máximas, símbolos y días.
3. El editor revisa las composiciones y exporta manualmente en H.264, 1920×1080 y 25 fps.

## Configuración inicial

1. Copia `.env.example` como `.env` y añade la API key de AEMET. También se admite
   una clave sin formato dentro de `api.txt`; ambos archivos están excluidos de Git.
2. Revisa las agrupaciones ya configuradas en `config/meteo.json`.
3. Ejecuta `python scripts/generate_daily.py --validate`.

La API key nunca debe incluirse en el proyecto de After Effects ni en el JSON diario.

## Generación diaria

```powershell
python scripts/generate_daily.py
```

Para reconstruir el JSON usando las descargas ya guardadas, sin volver a consultar AEMET:

```powershell
python scripts/generate_daily.py --reuse-raw
```

El programa realiza tres peticiones de producto a AEMET OpenData: predicción diaria de todos
los municipios, predicción horaria de todos los municipios y avisos CAP de España. AEMET
OpenData no publica el mapa gráfico de máximas, así que el programa consulta además la página
oficial de temperaturas y descarga desde allí las imágenes vigentes de Península y Baleares
y de Canarias. Los originales se conservan en `data/raw/AAAA-MM-DD/` para poder auditar el
resultado.

El mapa de alertas es un PNG RGBA de 1920×1080 con fondo transparente. Parte todas las zonas
en verde y aplica el nivel máximo activo de cada zona AEMET: amarillo, naranja o rojo. Para la
generación diaria ya no hace falta abrir `MAPA_ALERTAS.fla` ni seleccionar colores a mano.

Después, con `METEO FINAL.aep` abierto, ejecuta en After Effects:

`Archivo > Secuencias de comandos > Ejecutar archivo de secuencia de comandos...`

y selecciona `tools/apply_daily_data.jsx`.

## Ejecucion diaria completa

La tarea de Codex `Meteo diario AEMET — ejecutar al llegar` esta guardada y pausada,
sin hora de activacion efectiva. Esto evita perder la ejecucion si el ordenador esta
apagado a una hora concreta.

Al llegar a la redaccion, el editor debe:

1. Encender el PC y abrir Codex.
2. Entrar en `Programadas`.
3. Abrir `Meteo diario AEMET — ejecutar al llegar`.
4. Pulsar `Ejecutar ahora` y mantener Codex abierto hasta que termine.

La tarea descarga los datos de AEMET, genera y verifica los dos compuestos finales
siguiendo los flujos de temperatura y alertas y, solo cuando todo esta listo, abre
`METEO FINAL.aep` en After Effects y ejecuta `tools/apply_daily_data.jsx`.

El lanzador local usado internamente por la tarea es `scripts/run_daily.ps1`. Sus fases
tecnicas tambien se pueden ejecutar manualmente para diagnostico:

```powershell
# Descargas, JSON y mapas tecnicos
powershell -ExecutionPolicy Bypass -File scripts/run_daily.ps1 -Stage Prepare

# Validacion de los compuestos finales y apertura en After Effects
powershell -ExecutionPolicy Bypass -File scripts/run_daily.ps1 -Stage Apply

# Comprobar las salidas finales sin abrir After Effects
powershell -ExecutionPolicy Bypass -File scripts/run_daily.ps1 -Stage Apply -NoLaunch
```

`Stage All` sirve para ejecutar ambas fases seguidas cuando los compuestos finales de
la fecha ya existen. El script local no sustituye la tarea de Codex, porque la creacion
y la inspeccion visual de los compuestos finales requieren sus skills de imagen. El
script nunca reutiliza silenciosamente imagenes de otro dia:
comprueba la fecha del JSON, la presencia de todas las fuentes y que `alertas.png`,
el mapa tecnico, mida 1920x1080. `temperaturas_final.png` es obligatorio y debe
conservar los 1672x941 pixeles de la base 3D. `alertas_final.png` se valida con esas
mismas dimensiones cuando existe; si no hay avisos activos puede omitirse y After
Effects desactiva la capa de `ALERTAS` para no mostrar un mapa anterior. Los registros
quedan en `logs/daily-AAAA-MM-DD.log`.

### Compuesto de temperaturas vigente

Antes de crear el mapa final se prepara la textura registrada de la fecha:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/update_temperature_template.ps1 -Stage Prepare -Date AAAA-MM-DD -NoLaunch
```

Este paso valida la cobertura y la paleta, y publica en `data/generated/AAAA-MM-DD/`
dos texturas. Para la composición asistida debe utilizarse exclusivamente
`temperatura_con_limites.png`: contiene la temperatura registrada, las provincias en
casi negro `#020200` y las comunidades/costa en gris carbón `#202122`. No se deben
usar como referencia visual ni `temperatura_rellenada.png`, que no contiene esa red,
ni los mapas AEMET originales, cuya proyección no coincide con la perspectiva 3D.

El resultado aprobado se guarda como `temperaturas_final.png` a `1672 x 941`, que es
el tamaño que aún espera `METEO FINAL.aep`. Después se ejecuta `run_daily.ps1 -Stage
Apply -NoLaunch` para comprobarlo antes de abrir After Effects. El publicador de la
plantilla nueva a `1920 x 1080` no debe reemplazar este flujo hasta adaptar el proyecto
principal.

After Effects 2026 se detecta automaticamente. El envoltorio
`tools/open_and_apply_daily_data.jsx` abre el proyecto, ejecuta el JSX diario y deja el
proyecto abierto para revision. Si After Effects ya contiene otro proyecto, se detiene
sin cerrarlo ni descartarlo.

## Criterios actuales

- Ámbito: Península, Canarias y Baleares.
- Temperaturas: máxima más alta prevista entre las capitales de cada grupo.
- `PREVISION`: mañana a las 12:00.
- `DOBLE`: mañana y pasado mañana a las 12:00.
- Los códigos AEMET de intervalos nubosos con lluvia (23 y 43) usan `SOL LLUVIA`.
- Cuando una zona contiene capitales con tiempo soleado y otras con lluvia, se usa
  `SOL LLUVIA`. En los demás casos se mantiene el símbolo más significativo según la
  prioridad: tormenta, nieve, lluvia, viento, nubes, sol y nubes, sol.
- Los metrajes configurados se importan automáticamente desde
  `(Material de archivo)/SIMBOLOS` si todavía no están dentro del proyecto de After Effects.
- Si la predicción horaria no alcanza las 12:00 de pasado mañana, se usa por orden
  `12-18`, `12-24` y `00-24` de la predicción diaria.
- La selección del fenómeno más significativo entre 07:00 y 19:00 queda preparada como mejora posterior.
- El JSON de alertas resume el nivel máximo activo por provincia y por zona AEMET durante las
  24 horas; las zonas conservan además los polígonos CAP usados para generar `alertas.png`.
- El renderizador usa `config/alert_zone_faces.illustrator.reference.json`, generado a
  partir de los nombres de objetos de Illustrator. Comprueba 182 códigos terrestres y 51
  marítimos; los marítimos conservan el sufijo `C` y solo se dibujan cuando tienen aviso.

## Mapa de alertas de Illustrator

`MAPA_ALERTAS_ILUSTRATOR.ai` es la fuente de geometría activa. Los nombres y códigos
de sus objetos se leen de los datos editables de Illustrator, no del orden de formas
`Fm...` del PDF. Las piezas agrupadas de una misma zona se conservan bajo un solo
código. Dos objetos tienen en el `.ai` un código duplicado de la zona contigua:
`611801` (Cuenca del Genil) y `681902` (Parameras de Molina). El constructor aplica
esas dos correcciones explícitas, contrastadas con la posición de los polígonos CAP;
no modifica el archivo `.ai`.
El PNG dibuja los límites de zonas de aviso en gris claro, los de provincias en
gris medio y los de comunidades autónomas en negro, por ese orden.

Para reconstruir la referencia tras guardar cambios en Illustrator:

```powershell
python -m pip install pypdf numpy pillow zstandard
python tools/build_illustrator_zone_reference.py --cap data/raw/2026-10-01/avisos_cap.data.tar
```

El constructor exige 182+51 códigos y guarda el hash del `.ai`; el generador diario
rechaza referencias obsoletas. Necesita `pypdf`, `numpy` y `zstandard` (o `libzstd`)
para leer los
datos editables. El renderizador diario solo necesita la referencia JSON y Pillow.
Los contornos pueden estar consolidados por Illustrator: se exige un mínimo de 50
objetos provinciales y 17 autonómicos, conservando todos sus polígonos internos.
Los 51 contornos marítimos, que no tienen nombre individual en el `.ai`, se
emparejan con CAP mediante controles geográficos terrestres, con ajuste separado
para Canarias. La referencia anterior de inventario y su auditoría de formas
partidas ya no son fuentes del generador diario.

## Plantilla heredada de Animate (archivo histórico)

La plantilla anterior está en `data/alert_map_template/DOMDocument.xml` y procede de
las capas `Capa_4` y `linea_sobre` del FLA entregado. Solo hay que regenerarla si se modifica
la geometría del mapa en Animate:

```powershell
python scripts/extract_alert_template.py
```

Si cambian las caras del Animate, hay que reconstruir también su correspondencia con las
zonas AEMET usando un paquete CAP completo:

```powershell
python tools/build_alert_zone_face_reference.py --cap data/raw/AAAA-MM-DD/avisos_cap.data.tar
```

Después se puede reconstruir y comprobar el PNG sin descargar de nuevo los datos:

```powershell
python scripts/generate_daily.py --reuse-raw --date 2026-09-30
```

## Pendientes editoriales

- Definir cuándo el viento sustituye al símbolo de estado del cielo.
- Definir nombres de salida y preset final de Media Encoder/After Effects.

La inspección del `.aep` confirma que en `DOBLE` las capas 15–28 y el texto 30 son el
primer día (mitad izquierda), mientras que las capas 1–14 y el texto 29 son el segundo
día (mitad derecha). Esta correspondencia ya está reflejada en la configuración de ejemplo.
