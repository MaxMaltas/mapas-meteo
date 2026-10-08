# Automatización diaria de METEO

El proyecto separa la obtención y tratamiento de datos de la edición en After Effects:

1. `scripts/generate_daily.py` consulta AEMET y crea `data/generated/latest/meteo.json`.
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

El programa realiza tres peticiones de producto: predicción diaria de todos los municipios,
predicción horaria de todos los municipios y avisos CAP de España. Los originales se conservan
en `data/raw/AAAA-MM-DD/` para poder auditar el resultado.

Después, con `METEO FINAL.aep` abierto, ejecuta en After Effects:

`Archivo > Secuencias de comandos > Ejecutar archivo de secuencia de comandos...`

y selecciona `tools/apply_daily_data.jsx`.

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
- El JSON de alertas ya resume el nivel máximo activo de las zonas AEMET de cada provincia
  durante las 24 horas. El gráfico se produce por separado en otro proyecto.

## Pendientes editoriales

- Definir cuándo el viento sustituye al símbolo de estado del cielo.
- Definir nombres de salida y preset final de Media Encoder/After Effects.

La inspección del `.aep` confirma que en `DOBLE` las capas 15–28 y el texto 30 son el
primer día (mitad izquierda), mientras que las capas 1–14 y el texto 29 son el segundo
día (mitad derecha). Esta correspondencia ya está reflejada en la configuración de ejemplo.
