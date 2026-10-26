# Work-to-do — RPA de actualización de precios de wishlist Amazon

## Objetivo de la primera versión

Construir un robot secuencial en Robot Framework que consulte los artículos de una wishlist de Amazon, extraiga su precio y disponibilidad actuales, los compare contra el último valor registrado y genere un histórico y reporte de cambios.

> **Restricción operativa:** el robot no debe intentar resolver ni eludir CAPTCHA, MFA, rate limiting ni otros mecanismos de protección de Amazon. Si se presentan, registrará el bloqueo y finalizará de forma controlada.

---

## Estado de agentes

| Ubicación consultada | Resultado | Acción |
|---|---|---|
| `/.agents` | No existe en el equipo | No fue posible delegar tareas a agentes externos desde esta ruta. La construcción se realizó en el proyecto actual. |

---

## Decisiones de Human-in-the-loop resueltas

- [x] Marketplace: `amazon.com.mx`.
- [x] Persistencia inicial: CSV.
- [x] Wishlist autorizada proporcionada durante la ejecución, sin almacenarla en archivos versionados.
- [x] La sesión se reutilizará únicamente desde un perfil local de Chrome ya autenticado.
- [x] Directorio de perfil identificado de forma local; no se versiona. Inyectar con `AMAZON_CHROME_USER_DATA_DIR`.
- [x] Se confirmó que no se almacenarán credenciales, cookies ni tokens en el proyecto.

---

## Componentes construidos

### Configuración y recursos

- [x] Reorientar `config/dev.yaml`, `config/uat.yaml` y `config/prod.yaml` a Amazon México.
- [x] Mantener la URL de wishlist vacía en YAML para exigir inyección en tiempo de ejecución.
- [x] Añadir parámetros para perfil Chrome, modo visible, timeout e histórico CSV.
- [x] Crear `resources/amazon/locators.yaml`.
- [x] Sustituir métricas de transacciones por métricas de artículos, cambios de precio y disponibilidad.
- [x] Corregir la colisión con la variable reservada de Robot Framework: los datos usan `${DATA_OUTPUT_DIR}`, no `${OUTPUT_DIR}`.

### Persistencia y comparación

- [x] Crear `libraries/PriceTracker.py`.
- [x] Normalizar precios de Amazon México.
- [x] Extraer ASIN de URLs cuando esté disponible.
- [x] Usar la URL como identificador alternativo cuando no se obtiene ASIN.
- [x] Comparar el precio actual contra el último registro.
- [x] Crear histórico acumulativo CSV y reporte CSV inmutable por ejecución.
- [x] Registrar productos sin precio o con errores sin abortar el lote.

### Navegación y flujo Robot Framework

- [x] Adaptar `browser_keywords.resource` para utilizar un perfil Chrome existente sin leer o guardar cookies.
- [x] Detectar login, CAPTCHA, robot check y páginas de error como fallos controlados.
- [x] Implementar extracción de tarjetas visibles mediante DOM.
- [x] Implementar `Actualizar Wishlist Amazon`.
- [x] Implementar resumen final de métricas.
- [x] Actualizar la tarea principal y `robot.yaml` para el actualizador de wishlist.

---

## Validaciones realizadas

| Validación | Resultado |
|---|---|
| Compilación de `PriceTracker.py` | Correcta |
| Normalización/comparación de precio MXN | Correcta: `MX$1,299.90` vs `1399.90` = `DECREASED`, delta `-100.00` |
| Instalación de dependencias en `.venv` | Correcta |
| Firma de `RPA.Browser.Selenium.Open Available Browser` | Confirmada: soporta `use_profile`, `profile_name`, `profile_path` y `sandbox` |
| Robot Framework `--dryrun` | Correcto: 1 tarea, 1 aprobada, 0 errores |
| Primera prueba web con perfil | Falló antes de navegar: `DevToolsActivePort file doesn't exist` |
| Segunda prueba web conservando sandbox Chrome | Falló con el mismo error antes de navegar |
| Cierre y resumen tras fallo | Corregido y verificado: teardown completo, sin ocultar el fallo principal |

---

## Bloqueo técnico actual

El perfil de Chrome se resuelve correctamente y no existían procesos residuales de Chrome/ChromeDriver. Sin embargo, ChromeDriver no logra iniciar Google Chrome 155 con el perfil reutilizado y finaliza antes de que el robot pueda visitar Amazon:

```text
BrowserNotFoundError:
session not created: DevToolsActivePort file doesn't exist
```

No se realizaron ni se realizarán modificaciones destructivas sobre datos de sesión, tales como borrar `Singleton*`, cookies, preferencias o archivos del perfil.

---

## Siguiente intervención humana requerida

Elegir una de las alternativas seguras siguientes:

1. **Perfil de automatización independiente (recomendado):**
   - Crear un perfil nuevo de Chrome.
   - Iniciar sesión manualmente en Amazon dentro de ese perfil.
   - Cerrar Chrome.
   - Proporcionar la ruta del directorio de datos y nombre del perfil para el robot.
   - Evita la contención y fragilidad del perfil cotidiano.

2. **Chrome iniciado manualmente para depuración remota:**
   - Iniciar Chrome manualmente con un puerto de depuración y el perfil autorizado.
   - El robot deberá configurarse para adjuntarse a esa instancia, sin abrir una segunda instancia del perfil.
   - Requiere una modificación adicional del keyword de navegador.

3. **Wishlist realmente pública:**
   - Proporcionar una URL que no redirija a login en una sesión nueva.
   - El robot podrá ejecutarse con un perfil limpio, sin datos de sesión.

---

## Ejecución prevista

Después de resolver el bloqueo de perfil, la ejecución usará variables inyectadas y no guardará el enlace de la wishlist en el repositorio:

```bash
.venv/bin/robot \
  --outputdir results/amazon-run \
  --variable 'AMAZON_WISHLIST_URL:<URL_AUTORIZADA>' \
  --variable 'AMAZON_CHROME_USER_DATA_DIR:<RUTA_DE_PERFIL>' \
  tasks/main_process.robot
```

Los resultados de negocio se guardarán en:

```text
data/output/amazon_wishlist_price_history.csv
data/output/amazon_wishlist_report_<UTC_TIMESTAMP>.csv
```

Los artefactos de Robot Framework se mantendrán separados en `results/`.

---

## Criterios de aceptación pendientes

- [x] El robot inicia usando configuración de entorno.
- [x] El robot valida sintaxis, imports y flujo en modo seguro.
- [ ] El robot abre la wishlist usando el contexto autorizado sin sesión aislada.
- [ ] Cada artículo procesado deja un registro con fecha, precio, moneda y estado.
- [ ] Los cambios de precio se calculan frente al último registro disponible.
- [ ] Se crean histórico y reporte CSV a partir de una ejecución web real.
- [x] Los errores de un artículo están aislados del resto del lote.
- [x] No se guardan credenciales ni datos de sesión sensibles en el repositorio.
- [x] Los bloqueos por CAPTCHA/MFA se reportan de forma controlada, sin intentar evadirlos.
