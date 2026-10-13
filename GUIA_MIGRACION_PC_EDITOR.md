# Guía de migración de Meteo al PC del editor

## Objetivo

Trasladar este proyecto a otro PC Windows y dejarlo operativo tanto manualmente como desde Codex en la aplicación de escritorio de ChatGPT, conservando:

- la descarga y normalización de datos de AEMET;
- la generación de los mapas diarios de temperaturas y alertas;
- las dos skills locales de Codex;
- la actualización del proyecto `METEO FINAL.aep` en After Effects;
- la tarea `Meteo diario AEMET — ejecutar al llegar`;
- los controles que impiden usar datos de otra fecha o abrir After Effects con entregables inválidos.

La estrategia recomendada es: **hacer primero una copia maestra completa, adaptar las rutas en el PC nuevo, validar manualmente y recrear la tarea de Codex al final**.

## 1. Estado de referencia de este PC

Datos comprobados el 8 de octubre de 2026:

| Elemento | Estado actual |
|---|---|
| Carpeta | `C:\Users\Aruba IA\Documents\APPS\Meteo` |
| Tamaño aproximado | 0,83 GB, 442 archivos |
| Control de versiones | No hay repositorio Git inicializado |
| Python | 3.14.7, 64 bits |
| Paquetes presentes | Pillow 12.3.0 y requests 2.34.2 |
| Paquetes opcionales ausentes | pypdf, numpy y zstandard |
| After Effects | 2026, versión 26.5 |
| Illustrator | 2026, versión 30.8.2 |
| Tests | 26 descubiertos: 22 correctos y 4 omitidos porque falta pypdf |
| Validación de configuración | Correcta |
| Prueba local sin abrir Adobe | Correcta para 2026-10-08 |
| Tarea de Codex | Existe, está pausada y se ejecuta manualmente al llegar |

### Riesgos que hay que resolver

1. **No basta con copiar solo el código.** `(Material de archivo)` ocupa unos 486,5 MB y contiene fondos y símbolos imprescindibles, pero está excluida por `.gitignore`.
2. **La clave AEMET no debe incluirse en una copia compartida.** Está en `.env` o `api.txt`; ambos están excluidos por `.gitignore`.
3. **Hay rutas absolutas del usuario actual en varios JSX.** La producción diaria depende especialmente de:
   - `tools/open_and_apply_daily_data.jsx`
   - `tools/apply_daily_data.jsx`
4. **La tarea y la regla de permisos actuales contienen la ruta y el identificador local de este PC.** Deben recrearse para la máquina nueva; no se deben copiar sin editar.
5. **La configuración global de Codex no es portable.** `%USERPROFILE%\.codex\config.toml` contiene rutas internas de la instalación, sesiones y runtimes de esta máquina.
6. **No existe un manifiesto de dependencias Python.** Conviene crearlo antes de considerar cerrada la migración.

## 2. Qué debe copiarse y qué debe recrearse

### Copiar con el proyecto

- `METEO FINAL.aep`
- `MAPA_ALERTAS_ILUSTRATOR.ai`
- `MAPA_ALERTAS.fla`
- `(Material de archivo)` completa
- `config`, `meteo_pipeline`, `scripts`, `tools`, `tests`
- `temperature_template`
- `.codex/skills` completa
- `README.md` y esta guía
- `data/generated` y `data/raw`, al menos para conservar una fecha conocida de prueba
- los backups que se quieran conservar

Las carpetas `logs`, `tmp`, `output` y los `__pycache__` no son necesarias para operar, aunque se pueden archivar para auditoría.

### Transferir aparte y de forma segura

- `.env` o `api.txt` con la clave de AEMET.

Usar un gestor de contraseñas, un dispositivo cifrado o un canal seguro. No enviar la clave por correo ni incluirla en un ZIP compartido.

### Recrear en el PC nuevo

- inicio de sesión de ChatGPT/Codex;
- confianza y permisos del proyecto;
- tarea programada de Codex;
- regla de permisos para la fase `Prepare`;
- configuración personal de editor, terminal y notificaciones;
- posibles conexiones o plugins asociados a la cuenta del editor.

No copiar en bloque `%USERPROFILE%\.codex` desde el PC antiguo.

## 3. Elegir la ruta de destino

### Opción recomendada: ruta neutral

Usar:

```text
C:\Meteo
```

Evita que el proyecto dependa del nombre de usuario de Windows. Antes de la primera ejecución habrá que sustituir las rutas absolutas antiguas en los JSX activos.

### Opción rápida: reproducir la ruta actual

Usar exactamente:

```text
C:\Users\Aruba IA\Documents\APPS\Meteo
```

Solo es razonable si el usuario de Windows y la estructura del nuevo PC coinciden. Reduce cambios iniciales, pero mantiene una dependencia frágil y no es la opción aconsejada para producción.

## 4. Preparación en el PC actual

1. Elegir un momento sin edición diaria en curso.
2. Cerrar After Effects, Illustrator y el proyecto en cualquier otro programa.
3. Confirmar que los archivos del último día correcto están guardados.
4. No borrar ni modificar el PC antiguo durante la migración.
5. Crear una copia maestra completa, sin secretos, en un SSD externo o almacenamiento privado.

Ejemplo con una unidad externa `E:`:

```powershell
robocopy "C:\Users\Aruba IA\Documents\APPS\Meteo" "E:\Meteo_transfer" /E /COPY:DAT /DCOPY:DAT /R:2 /W:2 /XF ".env" "api.txt" "*.pyc" /XD "__pycache__" "tmp"
if ($LASTEXITCODE -ge 8) { throw "La copia ha fallado con codigo $LASTEXITCODE" }
```

No usar `/MIR`: podría borrar archivos del destino si se repite el proceso con una selección distinta.

### Verificación de integridad

En el PC actual, crear un inventario de hashes dentro de la copia de transferencia:

```powershell
Get-ChildItem "E:\Meteo_transfer" -File -Recurse |
  Get-FileHash -Algorithm SHA256 |
  Export-Csv "E:\Meteo_transfer_sha256.csv" -NoTypeInformation -Encoding UTF8
```

Como mínimo, comprobar manualmente que la copia contiene:

```text
E:\Meteo_transfer\.codex\skills\generate-daily-alert-map\SKILL.md
E:\Meteo_transfer\.codex\skills\generate-daily-temperature-map\SKILL.md
E:\Meteo_transfer\(Material de archivo)\bg\ALERTAS.png
E:\Meteo_transfer\(Material de archivo)\bg\TEMPERATURAS.png
E:\Meteo_transfer\METEO FINAL.aep
E:\Meteo_transfer\scripts\run_daily.ps1
```

## 5. Instalación base en el PC del editor

1. Actualizar Windows y los controladores gráficos.
2. Instalar la [aplicación de escritorio de ChatGPT para Windows](https://learn.chatgpt.com/docs/windows/windows-app). También se puede instalar con:

   ```powershell
   winget install --id 9PLM9XGG6VKS -s msstore
   ```

3. Iniciar sesión con la cuenta y el espacio de trabajo autorizados para usar Codex.
4. Instalar Python 3.14 de 64 bits y marcar la opción para añadirlo a `PATH`.
5. Instalar After Effects 2026. La versión de referencia probada es 26.5.
6. Instalar Media Encoder si se seguirá exportando manualmente en H.264.
7. Instalar Illustrator 2026 si el editor va a modificar o reconstruir la geometría del mapa. No es imprescindible para la ejecución diaria normal.
8. Instalar Git, aunque la primera transferencia se haga por copia. La aplicación usa Git para revisión de cambios y trabajo aislado.

Comprobaciones:

```powershell
python --version
Get-Command python
Get-Item "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.exe"
```

## 6. Copiar y preparar el proyecto

1. Copiar `E:\Meteo_transfer` a `C:\Meteo`.
2. Dar al usuario del editor control de lectura y escritura sobre `C:\Meteo`.
3. Copiar la clave AEMET por el canal seguro elegido y crear:

   ```text
   C:\Meteo\.env
   ```

   con este formato:

   ```dotenv
   AEMET_API_KEY=clave_real_del_editor
   ```

4. No guardar la clave dentro del `.aep`, los JSON diarios, las skills ni la tarea de Codex.

### Dependencias Python

Para reproducir el flujo diario y habilitar también las herramientas de reconstrucción:

```powershell
Set-Location C:\Meteo
python -m pip install --upgrade pip
python -m pip install Pillow==12.3.0 pypdf numpy zstandard
```

El flujo diario usa Pillow. `pypdf`, `numpy` y `zstandard` son necesarios para reconstruir y auditar la referencia del Illustrator. Los tests usan `unittest`, incluido con Python.

Como mejora inmediata de portabilidad, crear después un `requirements.txt` validado y versionado. No confiar indefinidamente en una instalación manual no documentada.

## 7. Adaptar las rutas absolutas

Si la carpeta nueva es `C:\Meteo`, sustituir:

```text
C:/Users/Aruba IA/Documents/APPS/Meteo
```

por:

```text
C:/Meteo
```

en los archivos activos que corresponda. Los más importantes son:

```text
tools/apply_daily_data.jsx
tools/open_and_apply_daily_data.jsx
tools/test_apply_daily_data.jsx
tools/inspect_project.jsx
temperature_template/project/update_temperature_daily.jsx
temperature_template/project/render_temperature_template.jsx
temperature_template/project/open_and_update_temperature_template.jsx
temperature_template/project/install_real_dem_relief.jsx
temperature_template/project/create_temperature_template.jsx
temperature_template/project/run_install_real_dem_relief_silent.jsx
temperature_template/project/run_create_temperature_template_silent.jsx
temperature_template/project/validate_temperature_template.jsx
```

`temperature_template/project/update_request.json`, `render_request.json`, los manifiestos y los logs pueden contener rutas históricas o generadas. No usar un reemplazo masivo dentro de logs o validaciones antiguas; los archivos de petición activos se regeneran al ejecutar los PowerShell.

También revisar las rutas fijas de After Effects en:

```text
scripts/run_daily.ps1
scripts/update_temperature_template.ps1
scripts/publish_temperature_template.ps1
```

`run_daily.ps1` busca otras instalaciones de After Effects si no encuentra la versión preferida. Los otros dos scripts de plantilla esperan actualmente After Effects 2026 en `C:\Program Files\Adobe`.

### Mejora recomendada antes del cierre

Convertir los JSX activos para que calculen la raíz a partir de la ubicación del propio script o de un único archivo de configuración. Así una futura migración no exigirá editar una docena de rutas. Esta mejora debe probarse en ambos PCs antes de retirar el antiguo.

## 8. Abrir el proyecto en Codex

La documentación oficial indica que la aplicación puede abrir una carpeta local y leer o modificar sus archivos. Véanse el [Quickstart](https://learn.chatgpt.com/docs/quickstart) y la guía de [entornos locales](https://learn.chatgpt.com/docs/environments/local-environment).

1. Abrir la aplicación de escritorio de ChatGPT.
2. Seleccionar **Codex**.
3. Pulsar **Add new project** o `Ctrl+O`.
4. Seleccionar `C:\Meteo`.
5. Revisar el contenido y marcar el proyecto como de confianza.
6. Empezar con permisos de escritura limitados al proyecto (`workspace-write` o su equivalente visible en la app).
7. Mantener **Ask for approval** para acciones que salgan del proyecto, accedan a la red o abran aplicaciones, hasta completar la validación.
8. Abrir una tarea nueva después de copiar o editar skills, para que Codex vuelva a descubrirlas.

La carpeta `.codex/skills` debe permanecer dentro del proyecto. Pedir a Codex:

```text
Enumera las skills locales disponibles para este proyecto Meteo y resume cuándo usarías cada una.
```

La respuesta debe incluir:

- `generate-daily-alert-map`
- `generate-daily-temperature-map`

Las instrucciones duraderas del proyecto pueden documentarse además en un `AGENTS.md` raíz. Codex carga estas instrucciones antes de trabajar y permite que viajen con el proyecto; consultar la [guía oficial de AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## 9. Pruebas de aceptación, en orden

Ejecutar desde `C:\Meteo`.

### 9.1 Configuración

```powershell
python scripts/generate_daily.py --validate
```

Resultado esperado:

```text
Configuración válida
```

### 9.2 Tests

```powershell
python -m unittest discover -s tests -v
```

Resultado esperado: 26 tests descubiertos. En el PC de referencia, 22 pasan y 4 se omiten por falta de `pypdf`; con las dependencias completas no deberían omitirse por ese motivo.

### 9.3 Prueba offline con datos conocidos

Esta prueba no descarga datos ni abre After Effects:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_daily.ps1 -Stage Apply -NoLaunch -Date 2026-10-08
```

Resultado esperado:

- valida `meteo.json` y las fuentes fechadas;
- valida siempre `temperaturas_final.png` y, cuando hay avisos activos, también `alertas_final.png`;
- termina con `Flujo diario completado`;
- no abre After Effects.

### 9.4 After Effects y metrajes

1. Abrir manualmente `C:\Meteo\METEO FINAL.aep`.
2. Comprobar que no haya metrajes ausentes.
3. Si After Effects no localiza un recurso, relocalizarlo dentro de `C:\Meteo\(Material de archivo)` y guardar el proyecto en la nueva ruta.
4. Verificar las composiciones `TEMP`, `PREVISION`, `DOBLE` y `ALERTAS`.
5. Cerrar After Effects antes de la prueba automática.

### 9.5 Aplicación automática en After Effects

Usar primero una fecha ya validada:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_daily.ps1 -Stage Apply -Date 2026-10-08
```

Debe abrir `METEO FINAL.aep`, ejecutar `tools/open_and_apply_daily_data.jsx` y dejar el proyecto abierto para revisión. No continuar si aparecen metrajes ausentes o alertas de scripts.

### 9.6 Descarga real

En un día de prueba y con la clave AEMET ya instalada:

```powershell
$fecha = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, "Romance Standard Time").ToString("yyyy-MM-dd")
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_daily.ps1 -Stage Prepare -Date $fecha
```

Comprobar:

- `data/raw/AAAA-MM-DD` contiene entradas nuevas;
- `data/generated/AAAA-MM-DD/meteo.json` tiene la fecha correcta;
- `alertas.png` mide 1920×1080;
- las imágenes térmicas proceden de la fecha actual;
- el log `logs/daily-AAAA-MM-DD.log` no contiene errores.

### 9.7 Flujo visual de Codex

En una tarea nueva de Codex, ejecutar primero cada skill por separado para la fecha del día. Revisar visualmente ambas imágenes finales antes de probar el flujo combinado:

```text
Usa $generate-daily-temperature-map para la fecha de hoy en Europe/Madrid y no abras After Effects.
```

```text
Usa $generate-daily-alert-map para la fecha de hoy en Europe/Madrid y no abras After Effects.
```

El editor debe confirmar:

- fidelidad de colores AEMET;
- zonas de alerta correctas;
- límites y título intactos;
- ausencia de leyendas, etiquetas o fondos importados;
- archivos finales en `data/generated/AAAA-MM-DD`.

## 10. Recrear la tarea de Codex

Las tareas que usan archivos locales necesitan que el PC esté encendido y la aplicación abierta. La documentación oficial también recomienda probar el prompt manualmente antes de programarlo y empezar con los permisos más estrechos posibles; consultar [Scheduled tasks](https://learn.chatgpt.com/docs/automations).

No copiar directamente `automation.toml`: contiene el `project_id`, la ruta y metadatos del PC antiguo.

Después de superar todas las pruebas anteriores:

1. Abrir una tarea de Codex dentro del proyecto `C:\Meteo`.
2. Pedir que cree una tarea local con el nombre:

   ```text
   Meteo diario AEMET — ejecutar al llegar
   ```

3. Mantenerla **pausada**, porque el flujo editorial actual consiste en pulsar **Ejecutar ahora** al llegar.
4. Seleccionar el proyecto local `C:\Meteo` y un modelo disponible que soporte las herramientas visuales requeridas.
5. Usar este prompt, cambiando solo la ruta si se eligió otra carpeta:

```text
Ejecuta el flujo meteorológico diario completo en el proyecto Meteo para la fecha actual de Europe/Madrid. Trabaja desde la raíz del proyecto. Usa la skill generate-daily-temperature-map y, solo cuando el JSON indique avisos activos, la skill generate-daily-alert-map; respeta íntegramente sus fuentes autoritativas, fidelidad de color, comprobaciones visuales y límites de fallo. Primero ejecuta `powershell -NoProfile -ExecutionPolicy Bypass -File "C:/Meteo/scripts/run_daily.ps1" -Stage Prepare -Date YYYY-MM-DD`, sustituyendo YYYY-MM-DD por la fecha de Madrid; esta fase debe descargar datos frescos de AEMET y crear el JSON, el mapa técnico de alertas y las fuentes térmicas. Después crea y verifica visualmente `data/generated/YYYY-MM-DD/temperaturas_final.png`. Si hay avisos activos, crea y verifica también `data/generated/YYYY-MM-DD/alertas_final.png`; si no los hay, no generes ese archivo. No uses datos ni imágenes finales de otra fecha y no sobrescribas una salida correcta con un resultado fallido. Cuando las imágenes requeridas para ese día existan y hayan superado la inspección visual, ejecuta `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_daily.ps1 -Stage Apply -Date YYYY-MM-DD`; esta fase valida los archivos, abre `METEO FINAL.aep` en After Effects y ejecuta `tools/apply_daily_data.jsx`. Si cualquier descarga, generación, inspección o validación falla, no abras After Effects y comunica el archivo o paso exacto que falló. Al terminar, informa de la ruta del mapa de temperaturas, de la ruta del mapa de alertas cuando corresponda, y confirma si After Effects se abrió y el JSX se ejecutó.
```

6. Ejecutarla manualmente una vez mientras el responsable técnico está presente.
7. Mantener el PC antiguo disponible hasta completar al menos tres ejecuciones correctas en días distintos.

## 11. Regla de permisos de red

La fase `Prepare` necesita acceder a AEMET. En el PC actual existe una regla limitada exclusivamente a ese prefijo. En el nuevo PC debe recrearse con la ruta nueva, no copiarse sin editar.

Archivo sugerido:

```text
%USERPROFILE%\.codex\rules\meteo-prepare.rules
```

Contenido para `C:\Meteo`:

```text
prefix_rule(
    pattern = [["powershell", "powershell.exe"], "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "C:/Meteo/scripts/run_daily.ps1", "-Stage", "Prepare", "-Date"],
    decision = "allow",
    justification = "Allow only Meteo daily Prepare to download current AEMET data.",
    match = [
        "powershell -NoProfile -ExecutionPolicy Bypass -File 'C:/Meteo/scripts/run_daily.ps1' -Stage Prepare -Date 2026-10-08",
    ],
    not_match = [
        "powershell -NoProfile -ExecutionPolicy Bypass -File 'C:/Meteo/scripts/run_daily.ps1' -Stage Apply -Date 2026-10-08",
        "powershell -NoProfile -ExecutionPolicy Bypass -File 'C:/Meteo/scripts/run_daily.ps1' -Stage All -Date 2026-10-08",
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_daily.ps1 -Stage Prepare -Date 2026-10-08",
    ],
)
```

Reiniciar la aplicación después de crear o cambiar la regla. La fase `Apply`, que abre After Effects, debe seguir quedando fuera de esta autorización automática limitada.

## 12. Operación diaria del editor

1. Encender el PC y abrir la aplicación de ChatGPT.
2. Abrir **Scheduled/Programadas**.
3. Seleccionar `Meteo diario AEMET — ejecutar al llegar`.
4. Pulsar **Ejecutar ahora**.
5. Mantener la aplicación y el PC encendidos.
6. No abrir otro proyecto en After Effects mientras se ejecuta el flujo.
7. Revisar las dos imágenes finales y el log del día.
8. Revisar `METEO FINAL.aep` abierto por el script.
9. Exportar manualmente en H.264, 1920×1080 y 25 fps según el flujo editorial vigente.

## 13. Vuelta atrás y cierre de la migración

Durante la primera semana:

- conservar el PC antiguo sin cambios como respaldo;
- evitar trabajar en ambos PCs el mismo día;
- guardar el resultado de cada ejecución y su log;
- comparar visualmente al menos tres días;
- documentar cualquier diferencia de fuentes, plugins, Adobe o permisos.

La migración se considera aceptada cuando:

- [ ] el inventario de archivos críticos coincide;
- [ ] la clave AEMET funciona y no está en una copia compartida;
- [ ] Python y las dependencias están instalados;
- [ ] los 26 tests terminan correctamente;
- [ ] `--validate` termina correctamente;
- [ ] la prueba `Apply -NoLaunch` termina correctamente;
- [ ] After Effects encuentra todos los metrajes;
- [ ] las dos skills aparecen en Codex;
- [ ] ambas imágenes finales superan la revisión visual;
- [ ] la aplicación automática deja el `.aep` listo para revisión;
- [ ] la tarea de Codex apunta al proyecto y ruta nuevos;
- [ ] la regla solo autoriza `Prepare` y no `Apply` ni `All`;
- [ ] se han completado tres días de producción correctos en el PC nuevo.

Solo entonces se debe archivar el PC anterior.

## 14. Mejoras recomendadas después de la migración

1. Inicializar un repositorio Git privado.
2. Usar Git LFS para `.aep`, `.ai`, `.fla`, `.mov` y otros binarios grandes.
3. Mantener los secretos fuera de Git.
4. Añadir y validar `requirements.txt`.
5. Eliminar las rutas absolutas de los JSX activos.
6. Crear un `AGENTS.md` pequeño con comandos de prueba, reglas de seguridad y criterios de entrega.
7. Definir acciones del entorno local para `Validar`, `Tests` y `Prueba sin Adobe`; la aplicación permite guardar estas acciones bajo `.codex` y compartirlas con el proyecto.
8. Añadir un procedimiento de backup periódico de los originales Adobe y de los entregables diarios.
