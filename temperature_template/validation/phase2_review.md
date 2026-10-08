# Revisión de la Fase 2

Fecha: 2026-10-06

Estado: completada y aprobada por el usuario.

## Comprobaciones superadas

- Todos los activos tienen `1672 x 941` píxeles.
- `fondo_titulo.png` coincide byte a byte con la base visual original.
- `superficie_original.png`, `bordes_brillos.png`, `laterales_sombras.png` y
  `relieve.png` contienen un canal alfa real.
- La máscara principal no colorea los laterales del mapa en la prueba plana.
- Península, Baleares, Canarias y el pequeño enclave inferior quedan representados.
- Ningún píxel de la referencia coloreada se copia en los activos estáticos.
- La imagen base y el proyecto de producción permanecen sin cambios.

## Decisiones de construcción

- `fondo_titulo.png` conserva intencionadamente la base completa, incluido el mapa
  gris. Actúa como fondo de seguridad: la capa térmica ocultará las caras superiores
  y los laterales originales permanecerán intactos.
- La salida coloreada del 6 de octubre se utiliza únicamente para localizar las
  superficies que cambiaron. No aporta color, textura ni geometría a los activos.
- `relieve.png` contiene la luminancia suavizada de la superficie original, limitada
  por la máscara superior.
- `laterales_sombras.png` es todavía una región conservadora alrededor del volumen;
  no es necesario usarla para la primera plantilla porque la base completa ya
  preserva laterales y sombras.

## Revisión visual realizada

Se revisó `../assets/static/prueba_color_plano.png` comprobando:

1. Contorno de Galicia y costa cantábrica.
2. Pirineos y frontera con Francia.
3. Costa mediterránea y Andalucía.
4. Baleares.
5. Canarias.
6. Pequeño enclave inferior del mapa.
7. Divisiones internas visibles sobre el color naranja.

La primera propuesta contenía fragmentos de textura gris y azul en el oeste y
suroeste. Se limpiaron conservando únicamente componentes conectados de frontera y
protegiendo explícitamente Baleares, Canarias y los enclaves inferiores. La prueba
plana final quedó aprobada.

## Criterio para cerrar la fase

La máscara de superficie y la capa `bordes_brillos.png` están aprobadas. Puede
comenzar la calibración geográfica de la Fase 3.
