# Auditoría de correspondencias AEMET ↔ MAPA_ALERTAS.fla (2026-10-02)

Estado: investigación; **no usar** `provisional_reference.json` ni `alertas_provisional_2026-10-02.png` como mapa final.

## Hechos comprobados

- `MAPA_ALERTAS.fla` y la plantilla extraída `data/alert_map_template/DOMDocument.xml` contienen el mismo `DOMDocument.xml` (SHA-256 `d71e404239af5abc79ee4d540d448c160ca61be4409e2da8e1e10e3ba560ccc3`). El fallo no procede de haber extraído un FLA distinto.
- La tabla vigente se construyó minimizando distancia entre centroides proyectados. Tiene 200 asignaciones a 200 caras, pero 56 de esas asignaciones tienen un desplazamiento superior a 100 px. Por ejemplo, «Litoral gaditano» (`611103`) figura en la cara 183, que es Fuerteventura, y «Meseta de Segovia» (`674001`) figura en la cara 79, lejos de su polígono CAP.
- La igualdad de recuentos es accidental: un segundo fragmento diminuto de «Litoral sur de Tarragona» (`694304`) no tiene cara propia en el FLA; La Palma tiene cuatro caras en el FLA y tres fragmentos CAP. Forzar una biyección entre fragmentos y caras produce desplazamientos.
- En el CAP guardado para el 2 de octubre hay 64 zonas con avisos que tocan alguna hora de ese día. Si se excluyen los avisos caducados a las 05:12:40, hora en que se generó `meteo.json`, quedan 59. Cambian de nivel nueve códigos: `622203`, `624403`, `625003`, `692503`, `694301`, `771201`, `771203`, `774602`, `774604`.
- El GeoJSON descargado de AEMET el 2 de octubre (`geojson_1790910000.tar.gz`) contiene dos archivos de resumen diario `r_D+0`, con 58 zonas de Península/Baleares y una de Canarias. Los 59 códigos y sus niveles coinciden **exactamente** con el CAP filtrado a las 05:12:40. El CAP de jornada completa difiere precisamente en los nueve códigos anteriores.
- El GeoJSON y el CAP comparten la elaboración `2026-10-01T21:50:01Z`; la divergencia de datos no procede de una nueva elaboración sino del tratamiento de avisos caducados. En el GeoJSON `Av_mayor` codifica `1=rojo`, `2=naranja`, `3=amarillo`.
- `scripts/generate_daily.py` ahora usa la hora actual de Madrid como corte al generar la fecha de hoy y permite fijar un corte reproducible con `--alerts-as-of`. Las fechas históricas mantienen el resumen de jornada completa salvo que se indique un corte.

## Material de revisión

- `face_audit_atlas.png`: todas las caras del FLA numeradas (0–199).
- `alertas_provisional_2026-10-02.png`: experimento con coincidencia de geometrías y filtro horario; **no validado**.
- `provisional_reference.json`: correspondencias candidatas de ese experimento; **no sustituye** a `config/alert_zone_faces.reference.json`.

## Contraste con los anexos oficiales de AEMET

- `METEOALERTA_ANX2_Zonas_aviso.pdf` (2022) contiene un catálogo de 182 zonas terrestres. Sus códigos coinciden exactamente con la referencia actual. La columna `mar=1` marca 51 zonas, exactamente las 51 que tienen código marítimo asociado terminado en `C`. Este anexo no ofrece mapas ni IDs de las caras del FLA.
- El documento oficial complementario `detalle_municipios_zonas_meteorologicas.pdf` (2017), guardado en `output/`, sí contiene mapas provinciales coloreados y leyendas con los códigos. Se han inspeccionado, entre otros, Segovia (p. 107), Burgos (p. 83), Soria (p. 112), Ávila (p. 78), Granada (p. 12), Almería (p. 4), Murcia (p. 220), Alicante (p. 164), Castellón (p. 168), A Coruña (p. 189), Lugo (p. 192), Ourense (p. 195), Canarias (pp. 46 y 48) y Baleares (p. 201).
- Una alineación geométrica local iterativa de los polígonos CAP con las caras FLA mejora la intersección media por cara de 0,463 a 0,635. Junto con el contraste visual provincial, la candidata `warped_reference.json` cubre las 200 caras, los 182 códigos terrestres y mantiene las 51 zonas marítimas. Cambia 55 códigos de cara respecto a la referencia vigente. **Sigue siendo una candidata, no la tabla de producción.**
- Contrastes de alta confianza: cara 56 = `674001` Meseta de Segovia; 59 = `674002` Sistema Central de Segovia; 79 = `674701` Meseta de Valladolid; 170 = `611804` Costa granadina; 171 = `611803` Nevada y Alpujarras; 172 = `610402` Nacimiento y Campo de Tabernas; 173–174 = `733005` Campo de Cartagena y Mazarrón. La antigua tabla situaba `674001` en la 79 y `733003` en la 173.

## Información externa que falta para cerrar las caras dudosas

Los anexos provinciales ya permiten revisar los grupos que motivaban la petición inicial de tooltips. Antes de promover `warped_reference.json` a producción conviene terminar la verificación de las caras pequeñas en el borde Galicia/León/Ourense, Ávila/Toledo y País Vasco/Cantabria. Los polígonos CAP y FLA no son topológicamente idénticos, por lo que una coincidencia automática 200↔200 no constituye prueba suficiente.
