# Revisión de fase 4: proyecto de After Effects

Fecha: 2026-10-06

Estado: proyecto creado y validado estructuralmente; pendiente de revisión visual
con After Effects abierto.

## Proyecto creado

- Archivo: `../project/Mapa_Temperaturas_Semiautomatico.aep`
- Composición: `TEMP_MAPA_MASTER`
- Formato: `1920 x 1080`, 25 fps, 10 segundos y 16 bits por canal.
- Tamaño del archivo: 176.269 bytes.
- SHA-256: `7BD311AE18745306FBFE37BFEF01F5141816075291F7AE9229C071CD674B23F7`.

El proyecto se construyó mediante ExtendScript dentro de After Effects 2026. El
registro `phase4_after_effects.log` confirma que la aplicación guardó la
composición con siete capas.

## Orden de capas

De arriba abajo:

1. `00_CONTROLES_PLANTILLA`
2. `05_LIMITES_COMUNIDADES_COSTA`
3. `04_LIMITES_PROVINCIAS`
4. `03_RELIEVE_PENDIENTE_DEM`
5. `02_TEMPERATURA_DIARIA`
6. `01_TIERRA_BASE`
7. `00_FONDO_GUIA`

La capa de relieve está desactivada intencionadamente. En esta fase solo reserva
la posición correcta de la pila; no se ha reutilizado el relieve del antiguo mapa,
porque pertenece a otra perspectiva y no coincide con el maestro cartográfico
aprobado.

## Automatización preparada

`../project/update_temperature_daily.jsx` lee la fecha diaria de
`../../data/generated/latest/meteo.json`, localiza
`assets/daily/FECHA/temperatura_rellenada.png`, reemplaza el metraje
`TEMPERATURA_DIARIA_REEMPLAZAR` y guarda el proyecto.

La capa de temperatura permanece desbloqueada para permitir el reemplazo. Tierra,
provincias, comunidades y fondo están bloqueados para evitar movimientos
accidentales.

## Validación estructural

Se comprobó en el archivo guardado la presencia de:

- la composición `TEMP_MAPA_MASTER`;
- los siete nombres de capa;
- el metraje reemplazable `TEMPERATURA_DIARIA_REEMPLAZAR`.

No se ha modificado `METEO FINAL.aep` ni ninguno de los archivos de producción.

## Siguiente paso

Generar una capa de sombreado topográfico a partir de un DEM real, registrarla
contra el maestro de 1920 x 1080 y conectarla al control `Intensidad relieve`.
Después se abrirá el proyecto para ajustar visualmente la intensidad y el modo de
fusión sin alterar los colores AEMET.
