# Auditoría de zonas partidas del mapa de Illustrator

Fuente: `MAPA_ALERTAS_ILUSTRATOR.ai` (SHA-256 `d402baa37b73e34f9870f8b308eea3f3baca4d11ac1d19dfd6817007d22a5d12`) y paquete CAP completo de AEMET de 2026-10-01. El CAP contiene 182 códigos terrestres; 18 tienen dos polígonos. El Illustrator contiene 195 formas terrestres. Unificar significa asignar **el mismo código a ambas formas** en la referencia, sin destruir ni fusionar los vectores originales.

## Coincidencias geométricas de zonas divididas

| Código AEMET | Zona | Formas del Illustrator |
| --- | --- | --- |
| 611101 | Grazalema | Fm57 + Fm58 |
| 611402 | Campiña cordobesa | Fm61 + Fm214 |
| 614103 | Sierra sur de Sevilla | Fm201 + Fm209 |
| 645301 | Ibiza y Formentera | Fm223 + Fm224 |
| 659101 | Lanzarote | Fm235 + Fm236 |
| 663903 | Centro y valle de Villaverde | Fm89 + Fm217 |
| 670503 | Sur de Ávila | Fm95 + Fm96 |
| 673702 | Sistema Central de Salamanca | Fm106 + Fm210 |
| 674701 | Meseta de Valladolid | Fm202 + Fm220 |
| 680202 | Alcaraz y Segura | Fm181 + Fm216 |
| 681301 | Montes del norte y Anchuras | Fm115 + Fm211 |
| 694304 | Litoral sur de Tarragona | Fm51 + Fm215 |
| 722801 | Sierra de Madrid | Fm148 + Fm222 |
| 733003 | Vega del Segura | Fm183 + Fm213 |
| 743102 | Centro de Navarra | Fm204 + Fm219 |
| 754802 | Bizkaia interior | Fm161 + Fm218 |
| 774601 | Interior norte de Valencia | Fm188 + Fm189 |

Estas 17 parejas coinciden en posición geográfica, separación entre fragmentos y superficie aproximada. Se han incorporado a la referencia de Illustrator con el estado `geometry_matched`. No son todavía una validación completa del mapa: las otras formas terrestres y las 51 marítimas siguen pendientes de identificación.

## Conflictos

| Código AEMET | Zona | Problema |
| --- | --- | --- |
| 674901 | Sanabria | El fragmento pequeño parece Fm221; el principal podría ser Fm111 o Fm145. No se asigna por ahora. |
| 690803 | Prelitoral de Barcelona | Falta una forma propia en el área correspondiente. |
| 690804 | Litoral de Barcelona | Falta una forma propia en el área correspondiente. |
| 691702 | Prelitoral de Girona | Falta una forma propia en el área correspondiente. |
| 691703 | Ampurdán | Falta una forma propia en el área correspondiente. |
| 691704 | Litoral sur de Girona | Falta una forma propia en el área correspondiente. |

Las cinco zonas ausentes de Barcelona y Girona se localizan en el hueco costero blanco del atlas; el trazado rojo en `output/illustrator_missing_zones_overlay.png` muestra su posición CAP aproximada. Es una inferencia geométrica, no una confirmación de que esas capas no existan ocultas en el proyecto editable de Illustrator. Conviene revisarlo allí antes de dibujar o copiar formas.

La generación diaria sigue usando la plantilla heredada de Animate. No debe activarse la referencia de Illustrator hasta completar y revisar todas las correspondencias.
