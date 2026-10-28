# Documento de Diseño: Plataforma Autónoma de RPA & DevOps (Robot Framework)

## 1. Intención y Propósito (Intent & Why)
Transformar el proyecto de automatización personal (hobby) basado en Robot Framework en una plataforma de grado de ingeniería: desatendida, autónoma y resiliente. El sistema debe operar 24/7 sin depender de mantener la máquina personal encendida, integrando alertas y control bidireccional mediante un bot de Telegram, orquestación ligera con soporte a MCP/IA determinista (bajo consumo de tokens, códigos de estado estrictos) y un ciclo completo de ingeniería de software con Continuous Integration y Continuous Delivery (DevOps).

Plazo objetivo: 2 meses (hito funcional antes de finalizar el año).

---

## 2. Metas, No-Metas y Anti-Metas (Goals, Non-Goals, Anti-Goals)

### Metas (Goals)
- **Ejecución Desatendida 24/7:** Despliegue de flujos en un entorno remoto o equipo dedicado (GitHub Actions programado / VPS de costo cero o Mini-PC/servidor local) sin requerir el equipo de uso diario encendido.
- **Canal de Interacción Telegram:** Bot de Telegram en primera línea para recibir alertas con el delta de precio y enlace, disparar ejecuciones (`/run wishlist`, `/status`) y manejar reautenticación bajo demanda.
- **Persistencia Externa de Precios:** Almacenamiento histórico en base de datos ligera (SQLite local o DB serverless gratuita tipo Turso/D1), desacoplada del DOM de Amazon para máxima velocidad y estabilidad.
- **Flujo HITL Asíncrono y Desacoplado:** Si la sesión caduca o requiere 2FA/CAPTCHA, el proceso falla rápido de forma controlada (`STATUS_NEEDS_2FA`), notificando a Telegram para que el usuario ejecute un flujo interactivo bajo demanda (`/login`) cuando esté disponible.
- **IA Determinista y Protocolo MCP:** 
  - La ejecución rutinaria es 100% código determinista en Robot Framework / Python (sin gasto innecesario de tokens).
  - La IA actúa exclusivamente como **triage sidecar** ante excepciones no controladas o anomalías en logs/reportes.
  - El servidor MCP expone herramientas estandarizadas con esquemas estrictos.
- **Resiliencia en dos capas:** Manejo de excepciones nativo y estructurado en Robot Framework (separación estricta entre *System Exceptions* y *Business Exceptions*) previo a cualquier intervención de IA o humana.
- **DevOps Integral (CI/CD):** 
  - **CI:** Linters estáticos (`robocop`, `robotidy`), pruebas unitarias (`pytest tests/`) y validación estática de tareas en cada Pull Request.
  - **CD:** Empaquetado automático (imagen Docker ligera) y despliegue continuo hacia el host/runner al fusionar a `main`.

### No-Metas (Non-Goals)
- No se desarrollará un chatbot conversacional denso; las interacciones son comandos y botones directos.
- No se forzará la escritura de notas dentro del DOM de Amazon (se reemplaza por base de datos externa para evitar bloqueos y dependencia de propiedad de la lista).
- No se contempla el soporte a procesos en modo gráfico interactivo para producción; todo operará en modo headless.
- No se realizarán compras automáticas en Amazon (exclusivamente monitoreo, analítica y alertas).

### Anti-Metas (Anti-Goals)
- **Dependencia de la máquina personal:** Cualquier arquitectura que requiera que la laptop del usuario permanezca encendida es inaceptable.
- **Costos recurrentes elevados en la nube:** Si la nube genera cobros recurrentes notables, la solución debe ejecutarse en hardware local dedicado (Mini-PC de bajo consumo).
- **Bloqueos sincrónicos en runners:** Nunca pausar un runner desatendido esperando respuesta humana en tiempo real (evita agotar minutos de CI o dejar procesos zombies).
- **Riesgo en cuenta personal:** No almacenar credenciales con medios de pago activos en entornos remotos.

---

## 3. Restricciones Técnicas y de Entorno (Constraints)
- **Framework base:** Robot Framework con Python 3.10+ y SeleniumLibrary / Browser (Playwright) ya presentes en el ecosistema.
- **Presupuesto:** 0 a mínimo costo mensual (aprovechar tiers gratuitos de GitHub Actions / Cloudflare / Turso, o hardware propio existente).
- **Canal de notificación:** Telegram Bot API (webhooks o long-polling ligero según el host de ejecución).
- **Compatibilidad headless:** Todos los scripts de navegación deben operar de forma estable en modo `--headless=new` en contenedores Linux.
- **Arquitectura existente:** Respetar la arquitectura en capas definida en `docs/ARCHITECTURE.md` (`tasks/`, `keywords/`, `libraries/`, `resources/`, `config/`).

---

## 4. Decisiones de Diseño Tomadas (Decided Parts)

### A. Estrategia de Rastreo y Datos (Recomendación Adoptada)
- **Wishlist pública/compartida:** La lista de deseos puede permanecer en tu cuenta principal o en una secundaria compartida mediante enlace.
- **Extracción de solo lectura:** El scraper se enfoca estrictamente en extraer el precio actual, título y disponibilidad sin modificar el DOM de notas de Amazon. Esto reduce drásticamente el tiempo de ejecución (hasta 5x más rápido) y elimina el 70% de la superficie de detección antibot.
- **Historial en Base de Datos:** Los precios se guardan en una base de datos ligera estructurada (`item_id`, `title`, `url`, `current_price`, `lowest_price`, `last_checked`, `notes`).
- **Alertas inteligentes:** Al detectar que `current_price < lowest_price`, se actualiza el registro y se dispara de inmediato la alerta formateada a Telegram con el porcentaje de ahorro.

### B. Ciclo de Autenticación y 2FA (Asíncrono Desacoplado)
- Las tareas programadas desatendidas se ejecutan sin intervención humana.
- Si una ejecución detecta que la sesión caducó o solicita 2FA/CAPTCHA:
  1. Emite un código de terminación controlado `STATUS_NEEDS_2FA`.
  2. El bot envía una notificación a Telegram: *"⚠️ Se requiere reautenticación. Ejecuta /login cuando estés listo."*
  3. El usuario, cuando tiene tiempo, ejecuta `/login` en Telegram, lo que inicia una sesión interactiva donde el usuario ingresa el código OTP recibido y las cookies se guardan en el volumen persistente.

### C. Topología de Control e IA Determinista
- **Ruta principal:** Telegram Bot -> Ejecutor Robot Framework -> Base de datos -> Telegram Bot (100% determinista, 0 costo en tokens).
- **Triage Sidecar (IA):** Solo cuando ocurre un error imprevisto (ej. Amazon cambió un selector o error de red), el archivo de log/captura se envía a un modelo Flash acotado con un prompt estructurado para categorizar la causa raíz y proponer la acción en Telegram.
- **Servidor MCP:** Expone herramientas modulares (`run_wishlist`, `get_history`, `check_health`) para permitir conectar la plataforma con otros clientes MCP o agentes externos cuando se desee.

### D. Pipeline DevOps (CI/CD)
- **CI (GitHub Actions en PR/Push):**
  - Linting y formateo con `robocop` y `robotidy`.
  - Pruebas unitarias de Python con `pytest tests/`.
  - Validación de sintaxis de suites `.robot`.
- **CD (GitHub Actions en merge a `main`):**
  - Construcción de imagen Docker optimizada.
  - Despliegue automático hacia el host de ejecución (Mini-PC self-hosted runner o entorno de nube).

---

## 5. Decisiones Técnicas Asumidas por el Constructor (Builder Calls)
1. **Motor de persistencia:** Se implementará una capa de datos agnóstica con interfaz estándar (`PriceRepository`), iniciando con SQLite local (con persistencia en volumen) y lista para conectarse a Turso (SQLite serverless) si se ejecuta en runners efímeros.
2. **Bot Runner:** El bot de Telegram operará como un servicio en segundo plano (daemon con python-telegram-bot) dentro del mismo entorno de ejecución o contenedor.
3. **Manejo de CAPTCHAs en Fase 1:** Si se detecta un CAPTCHA en ejecuciones programadas, se aplicará política de enfriamiento (*exponential backoff*) y alerta a Telegram, postergando soluciones de resolución por visión computacional para la siguiente fase.
