# Revisión de fase 7: render y publicación fechada

Fecha: 2026-10-07

Estado: completada y revisada visualmente.

## Salida publicada

- Archivo: `../../data/generated/2026-10-07/temperaturas_final.png`
- Dimensiones: `1920 x 1080`
- Tamaño: 1.481.029 bytes
- SHA-256: `896538FFCEBD91F5511706005CE03750DEC5802D50C6EB7ABCCAF312F362F486`
- Composición: `TEMP_MAPA_MASTER`
- Cobertura de la textura: `99,975 %`
- Colores meteorológicos inventados: `0`

La carpeta fechada también contiene las dos fuentes AEMET, la textura registrada
y `temperature_template_manifest.json` con hashes y trazabilidad.

## Método de render

After Effects no dispone en esta instalación de un preset PNG. El publicador elige
el preset disponible `Secuencia TIFF con alfa`, limita la cola a un fotograma y
convierte el TIFF resultante a PNG. El render se realiza primero en una carpeta
temporal; solo se publica tras validar que mide `1920 x 1080` y supera el tamaño
mínimo esperado.

Los elementos que ya estuvieran en la cola de render se desactivan en la sesión
temporal y el proyecto se cierra sin guardar esos cambios.

## Revisión visual

Se comparó el render con las fuentes AEMET de la misma fecha. Se comprobó:

- continuidad del patrón frío en Galicia, Cantábrica, Pirineos y centro;
- conservación de las zonas cálidas del Mediterráneo y el sur;
- delimitaciones provinciales y autonómicas visibles;
- relieve aplicado solamente a la Península;
- Baleares y Canarias sin desplazamiento ni relieve;
- ausencia de leyenda, marco, logotipos, Francia y norte de África.

## Integración diaria

`update_temperature_template.ps1` llama ahora al publicador después de actualizar
el metraje. Una ejecución normal produce el PNG fechado de principio a fin.

La salida nueva es `1920 x 1080`. El flujo antiguo de `METEO FINAL.aep` sigue
esperando un compuesto de `1672 x 941` y no se ha modificado en esta fase.
