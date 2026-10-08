# Revisión de fase 6: actualización diaria semiautomática

Fecha de validación: 2026-10-07

Estado: completada sobre copias de validación.

## Flujo implementado

`scripts/update_temperature_template.ps1` recibe una fecha y ejecuta estas
operaciones:

1. comprueba las dos fuentes AEMET correspondientes exactamente a esa fecha;
2. descarga fuentes solo cuando se solicita el día actual y todavía no existen;
3. ejecuta `build_daily_temperature_texture.py`;
4. valida dimensiones, cobertura y colores autorizados;
5. escribe una solicitud efímera para After Effects;
6. sustituye exclusivamente el metraje `TEMPERATURA_DIARIA_REEMPLAZAR`;
7. guarda el `.aep` y exige un registro de confirmación nuevo.

El lanzador se detiene si After Effects ya está abierto. Esto evita una escritura
simultánea sobre el mismo proyecto.

## Pruebas cartográficas

| Fecha | Cobertura | Píxeles residuales | Colores | Inventados |
| --- | ---: | ---: | ---: | ---: |
| 2026-09-30 | 99,975 % | 144 | 15 | 0 |
| 2026-10-02 | 99,975 % | 144 | 16 | 0 |

El 30 de septiembre contiene una situación claramente más cálida en el sur y
el 2 de octubre una penetración fría más extensa por el centro y este. Ambos
patrones conservaron su posición al utilizar exactamente los mismos 50 controles
geométricos.

## Pruebas de After Effects

Se crearon dos copias aisladas del proyecto:

- `after_effects_tests/Mapa_Temperaturas_validacion_2026-09-30.aep`
- `after_effects_tests/Mapa_Temperaturas_validacion_2026-10-02.aep`

After Effects confirmó el reemplazo y guardado de ambas mediante:

- `phase6_after_effects_update_2026-09-30.log`
- `phase6_after_effects_update_2026-10-02.log`

Las dos copias conservan `03_RELIEVE_DEM_REAL` y
`00_CONTROLES_PLANTILLA`. Sus binarios contienen la fecha diaria correcta.

## Protección del trabajo manual

El proyecto principal `project/Mapa_Temperaturas_Semiautomatico.aep` no se abrió
ni guardó durante estas pruebas. Conserva la fecha de modificación
`2026-10-06 11:01:07` y el SHA-256
`723CC41116AD66D22481E89A36FF2190577FE1E4697EBBD45C9821E56E96748B`.

La solicitud temporal utilizada para las pruebas se eliminó al terminar, para que
no pueda ejecutarse accidentalmente contra una copia histórica.
