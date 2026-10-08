# Revisión de fase 3: registro diario de temperaturas

Fecha de prueba: 2026-10-06

Estado: segunda versión corregida y aprobada visualmente por el usuario.

## Resultado

El script `scripts/build_daily_temperature_texture.py` transforma las dos imágenes
diarias de AEMET en una textura transparente de `1920 x 1080` encajada sobre el
maestro limpio.

Genera tres archivos en `assets/daily/FECHA/`:

- `temperatura_rellenada.png`: solamente el campo térmico y transparencia.
- `temperatura_con_limites.png`: temperatura, provincias y comunidades.
- `preview_registro.png`: vista de control sobre fondo azul claro.

## Decisiones técnicas

- La Península se registra como un único campo coherente mediante 47 anclajes
  detectados automáticamente, uno por provincia, más tres anclajes de contorno.
- La deformación es continua y se evalúa sobre una rejilla de ocho píxeles; las
  manchas térmicas no se recolocan individualmente.
- Mallorca, Menorca, Ibiza y Formentera se registran individualmente.
- Las siete islas canarias se registran individualmente.
- El remuestreo es por vecino más próximo para no crear tonos intermedios.
- En la Península no se aplica relleno general de costa. Solo se permite buscar un
  píxel real de la paleta a un máximo de tres píxeles del origen para atravesar el
  antialias y el grosor de las líneas cartográficas.
- No se aplica corrección de color, contraste, saturación ni iluminación.
- Los límites proceden del maestro limpio, no de las líneas comprimidas del PNG
  diario de AEMET.

## Validaciones superadas

- Dimensiones de salida: `1920 x 1080`.
- Provincias peninsulares emparejadas automáticamente: 47 de 47.
- Desviación inicial media antes de la corrección elástica: 18,45 píxeles.
- Desviación inicial máxima antes de la corrección elástica: 45,98 píxeles.
- Cobertura térmica: 579.791 de 579.935 píxeles (`99,975 %`).
- Píxeles transparentes residuales de borde: 144 (`0,025 %`). Se conservan
  transparentes en vez de inventar textura o extender manchas térmicas.
- Colores térmicos utilizados: 15.
- Colores ajenos a las paletas AEMET: 0.
- Península, cuatro islas baleares y siete islas canarias cubiertas.
- Script compilado correctamente con el Python instalado en el equipo.
- Tiempo de proceso medido en el equipo: aproximadamente 22 segundos.

## Corrección tras la primera revisión

La primera versión ajustaba el continente por el rectángulo exterior. Esto
estiraba los bordes, desplazaba el norte y obligaba a extender colores en Cataluña
y Cádiz. Esa estrategia se ha eliminado. La versión actual detecta las provincias
en ambas imágenes, resuelve su correspondencia uno a uno y genera una deformación
continua guiada por esa geometría.

La revisión posterior detectó un hueco de 1.146 píxeles en el Estrecho. El anclaje
usado para Tarifa, `(211,432)`, caía realmente sobre el mar gris de AEMET. Se ha
corregido al último extremo térmico real, `(188,431)`. El hueco conectado del
Estrecho ha desaparecido sin relleno plano ni colores nuevos.

## Validación multifecha

La misma transformación se comprobó posteriormente con `2026-09-30` y
`2026-10-02`. Ambas fechas conservaron una cobertura del `99,975 %`, cero colores
inventados y el mismo registro de 47 provincias más tres anclajes costeros.

## Pendiente antes de producción

Integrar, cuando se decida, esta plantilla independiente con el flujo general de
`METEO FINAL.aep`.

El flujo de producción actual no ha sido sustituido.
