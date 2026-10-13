# Revisión del maestro cartográfico limpio

Fecha: 2026-10-06

Estado: geometría registrada y estilo de límites aprobados visualmente.

## Fuente utilizada

El maestro se ha separado desde
`temperature_template/references/MAPA_ALERTAS_ILUSTRATOR.png`, exportación limpia
aprobada por el usuario. Se conserva su geometría ya registrada para impedir nuevos
desplazamientos y se aplican los colores medidos en la apariencia PDF del Illustrator
de producción: provincias `#020200` y comunidades/costa `#202122`.

## Salidas

- `mascara_temperatura.png`: máscara terrestre binaria.
- `tierra.png`: relleno blanco con transparencia exterior.
- `provincias.png`: límites provinciales casi negros `#020200` con transparencia.
- `comunidades.png`: costa y límites autonómicos gris carbón `#202122` con transparencia.
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

## Relación con el Illustrator

`MAPA_ALERTAS_ILUSTRATOR.ai` se conserva intacto como referencia editorial. Sus
últimos tonos de línea se midieron en la apariencia PDF y se aplicaron al maestro
térmico, pero no se sustituyó la geometría registrada por la rasterización directa
del `.ai`, ya que esa ruta alteraba el encaje aprobado.

El maestro térmico utiliza por tanto la exportación limpia registrada de
`temperature_template/references/` para la forma y el emplazamiento, y el Illustrator
actual solo como referencia de estilo. Esta separación permite oscurecer las líneas
sin desplazar provincias, costa ni campo térmico.

