# Plantilla determinista de temperaturas

Esta carpeta contiene el desarrollo aislado del nuevo mapa diario de temperaturas.
El flujo de producción actual debe seguir funcionando mientras se construye y valida
esta plantilla.

## Reglas de protección

- `../METEO FINAL.aep` es producción y no se modifica durante el desarrollo.
- `../(Material de archivo)/bg/TEMPERATURAS.png` es la base visual inmutable.
- Todo proyecto nuevo de After Effects se guardará en `project/`.
- Los recursos estáticos reconstruidos se guardarán en `assets/static/`.
- Las entradas o resultados diarios de prueba se guardarán en `assets/daily/`.
- Las imágenes para revisión humana se guardarán en `previews/`.
- Los informes y pruebas se guardarán en `validation/`.
- No se sustituirá el flujo actual hasta superar la validación con tres fechas.

## Estructura

```text
temperature_template/
├── assets/
│   ├── daily/
│   └── static/
├── previews/
├── project/
└── validation/
```

## Archivos estáticos previstos

La fase de separación visual generará, como mínimo:

- `assets/static/fondo_titulo.png`
- `assets/static/laterales_sombras.png`
- `assets/static/mascara_superficie.png`
- `assets/static/bordes_brillos.png`
- `assets/static/relieve.png`

La imagen original nunca será sobrescrita.

## Integración prevista

El proyecto nuevo trabajará primero de manera independiente. Cuando la salida haya
sido aprobada, podrá producir `data/generated/YYYY-MM-DD/temperaturas_final.png`
para que el proyecto principal lo consuma mediante la automatización existente.

## Estado

- Fase 1: completada el 2026-10-06.
- Fase 2: completada y aprobada el 2026-10-06.
- Maestro cartográfico limpio: generado y aprobado a `1920 x 1080`.
- Registro de temperaturas AEMET: generado y aprobado para `2026-10-06`.
- Proyecto independiente de After Effects: creado en
  `project/Mapa_Temperaturas_Semiautomatico.aep` con la composición
  `TEMP_MAPA_MASTER` y siete capas ordenadas.
- Sustitución diaria: preparada mediante
  `project/update_temperature_daily.jsx`.
- Relieve: generado a partir de ETOPO 2022 e instalado como
  `03_RELIEVE_DEM_REAL`. Por decisión editorial solo cubre la Península;
  Baleares y Canarias permanecen transparentes en esta capa.
- Control de relieve: el deslizador `Intensidad relieve` permite regularlo sin
  cambiar el archivo diario ni desplazar las delimitaciones.
- Producción general: todavía no sustituida. La plantilla y las tres fechas están
  validadas; falta decidir su integración con `METEO FINAL.aep`.

## Actualización diaria semiautomática

Con After Effects cerrado, ejecutar desde la raíz del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/update_temperature_template.ps1 -Date AAAA-MM-DD
```

El lanzador:

1. utiliza las fuentes AEMET existentes de esa fecha;
2. si la fecha es hoy y faltan, ejecuta la descarga diaria;
3. genera `assets/daily/FECHA/temperatura_rellenada.png`;
4. exige al menos 99 % de cobertura y cero colores inventados;
5. abre una instancia independiente de After Effects;
6. sustituye solo `TEMPERATURA_DIARIA_REEMPLAZAR` y guarda el proyecto;
7. renderiza el primer fotograma de `TEMP_MAPA_MASTER`;
8. valida y publica `data/generated/FECHA/temperaturas_final.png`.

Nunca descarga mapas actuales para completar una fecha histórica. Si After Effects
ya está abierto, se detiene para evitar que dos instancias guarden el mismo `.aep`.

Para generar y validar el PNG sin abrir After Effects:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/update_temperature_template.ps1 -Stage Prepare -Date AAAA-MM-DD -NoLaunch
```

## Validación diaria

- `2026-10-06`: aprobada visualmente por el usuario.
- `2026-09-30`: cobertura 99,975 %, cero colores inventados y reemplazo en copia
  de After Effects confirmado.
- `2026-10-02`: cobertura 99,975 %, cero colores inventados y reemplazo en copia
  de After Effects confirmado.

El proyecto principal no se utilizó en las pruebas de sustitución.

## Publicación del mapa final

El publicador independiente es `scripts/publish_temperature_template.ps1`. El
lanzador diario lo ejecuta automáticamente después de actualizar After Effects.

La salida de la nueva plantilla mide `1920 x 1080`. No debe utilizarse todavía con
el antiguo paso `scripts/run_daily.ps1 -Stage Apply`, que continúa esperando el
compuesto 3D anterior de `1672 x 941`. Esa conexión se hará solamente cuando se
apruebe la sustitución del flujo de producción.

Para actualizar el `.aep` sin publicar un render:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/update_temperature_template.ps1 -Date AAAA-MM-DD -NoPublish
```
