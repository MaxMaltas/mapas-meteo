# Revisión de fase 5: relieve geográfico real

Fecha: 2026-10-06

Estado: generado e instalado en After Effects; pendiente de aprobación visual.

## Resultado

Se ha generado `../assets/static/relieve_dem.png`, una capa RGBA de `1920 x
1080` con sombreado topográfico neutro. El relieve cubre exclusivamente la
Península. Baleares y Canarias son completamente transparentes en esta capa, por
lo que mantienen la textura térmica sin el desplazamiento que producía el escalado
independiente del relieve.

La vista de control está en `../previews/relieve_dem_preview.png`.

## Fuente y registro

- Elevación: NOAA NCEI ETOPO 2022, superficie, 60 segundos de arco con muestreo
  cada dos celdas.
- Iluminación: noroeste, escala de grises neutra alrededor de 128.
- Península: deformación continua con 47 centros provinciales y tres puntos de
  costa, idéntica al registro térmico aprobado.
- Baleares y Canarias: excluidas deliberadamente de la capa de relieve.

El relieve no contiene colores meteorológicos ni rellena huecos diarios. Es un
recurso estático independiente.

## Integración en After Effects

- Proyecto: `../project/Mapa_Temperaturas_Semiautomatico.aep`.
- Capa: `03_RELIEVE_DEM_REAL`.
- Metraje: `RELIEVE_DEM_REAL`.
- Posición: encima de `02_TEMPERATURA_DIARIA` y debajo de ambos niveles de
  delimitaciones.
- Fusión e intensidad: ajustadas manualmente por el usuario en After Effects.
- Opacidad indicada por el usuario: 50 %.
- Control: deslizador `Intensidad relieve` en `00_CONTROLES_PLANTILLA`.

After Effects confirmó la instalación en `phase5_after_effects.log`. El archivo
guardado contiene los nombres de composición, capa, metraje y control esperados.
Su SHA-256 actual es
`3E678679B0711892920E3FABB3FCD5B83628473CFEE9476F9455396D715695C9`.

## Revisión manual solicitada

Abrir `TEMP_MAPA_MASTER` y comprobar principalmente:

1. Que el relieve se percibe sin dominar los colores térmicos.
2. Que Pirineos, Cordillera Cantábrica, Sistema Central, Sistema Ibérico y
   Béticas resultan naturales.
3. Que Baleares y Canarias no reciben ningún sombreado del relieve.

Cambiar el control de intensidad no altera los PNG diarios ni el registro
geográfico.
