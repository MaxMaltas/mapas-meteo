# Revisión del maestro cartográfico limpio

Fecha: 2026-10-06

Estado: generado; pendiente de aprobación visual.

## Fuente utilizada

El maestro se ha separado desde
`temperature_template/references/MAPA_ALERTAS_ILUSTRATOR.png`, exportación limpia
aprobada por el usuario. El PNG contiene fondo transparente, tierra blanca,
comunidades oscuras y provincias grises, por lo que la separación por luminosidad
no requiere reconstruir geometría ni limpiar texturas.

## Salidas

- `mascara_temperatura.png`: máscara terrestre binaria.
- `tierra.png`: relleno blanco con transparencia exterior.
- `provincias.png`: límites provinciales grises con transparencia.
- `comunidades.png`: costa y límites autonómicos oscuros con transparencia.
- `mapa_maestro_transparente.png`: composición de las capas anteriores.
- `mapa_maestro_preview.png`: revisión sobre fondo azul claro.

Todos los archivos miden `1920 x 1080`. El PNG fuente se coloca sin reescalado en
la posición `(290, 74)` para evitar pérdida de detalle y mantener idénticas todas
las capas.

## Validaciones superadas

- Superficie terrestre: 579.935 píxeles.
- Límites provinciales: 7.984 píxeles visibles.
- Límites autonómicos y costa: 20.805 píxeles visibles.
- Todas las capas transparentes contienen alfa real.
- Todos los hashes registrados en `vector_master_manifest.json` coinciden.
- No se incluyen formas marítimas ni muestras de color.

## Advertencia sobre el Illustrator

El archivo actual `MAPA_ALERTAS_ILUSTRATOR.ai` no coincide con el hash de la
geometría validada de producción. Durante la comprobación, la lectura del archivo
actual devolvió 0 formas `ZONAS AEMET`, 62 de las 66 provincias y 27 de las 31
comunidades. No se ha modificado ni restaurado automáticamente porque podría
sobrescribir cambios del usuario.

El maestro térmico generado no depende del `.ai` actual: utiliza la exportación PNG
limpia conservada en `temperature_template/references/`.

