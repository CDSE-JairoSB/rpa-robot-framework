# Framework de Automatización RPA con Robot Framework

Arquitectura empresarial en capas para automatización de procesos robóticos (RPA) utilizando **Robot Framework** y **rpaframework**, diseñada bajo principios de mantenibilidad, resiliencia y estándares de calidad de software alineados a **ISTQB**.

---

## 📁 Estructura del Proyecto

La estructura separa cada automatización por **sitio objetivo**. Los recursos reutilizables permanecen en `common`; los que contienen reglas, locators o métricas propias de un portal se ubican dentro de su dominio.

```text
robotFramework/
├── config/                              # Configuración por ambiente
├── data/
│   ├── input/                           # Datos de entrada
│   └── output/                          # Reportes y datos generados
├── docs/                                # Arquitectura, QA y documentación operativa
├── keywords/
│   ├── amazon/                          # Lógica exclusiva de Amazon
│   │   ├── auth_flow.resource
│   │   ├── wishlist_notification.resource
│   │   └── wishlist_price_processing.resource
│   ├── insumoscerveceros/               # Keywords exclusivas del portal (cuando existan)
│   └── common/
│       └── system/                      # Interacciones técnicas reutilizables
│           ├── browser_keywords.resource
│           └── excel_keywords.resource
├── libraries/                           # Extensiones Python
├── resources/
│   ├── amazon/
│   │   └── locators.yaml                # Selectores exclusivos de Amazon
│   ├── insumoscerveceros/               # Variables/locators exclusivos del portal
│   └── common/
│       ├── locators/
│       │   └── portal_locators.yaml     # Locator genérico o legado, no asociado a un sitio
│       ├── variables/
│       │   └── global_variables.resource
│       └── settings.resource            # Librerías y recursos compartidos
├── results/                             # Evidencias y resultados de ejecución
├── tasks/
│   ├── amazon/
│   │   └── wishlist_amazon_price_updater.robot
│   ├── insumoscerveceros/
│   │   ├── insumoscerveceros_profile_sample.robot
│   │   └── insumoscerveceros_sample.robot
│   └── main_process.robot               # Orquestador del proceso Amazon actual
├── requirements.txt
└── robot.yaml
```

---

## 🚀 Inicio Rápido

### 1. Requisitos Previos
- Python 3.10+ instalado.
- Gestor de paquetes `pip` actualizado.

### 2. Creación de Entorno Virtual e Instalación
```bash
# Crear entorno virtual
python3 -m venv .venv

# Activar entorno (macOS / Linux)
source .venv/bin/activate
# En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

---

## ⚙️ Modos de Ejecución

### Parámetros locales (no versionar)

Las URLs de wishlist, rutas de perfil de Chrome y cualquier dato de sesión **no se versionan**. El robot las resuelve en este orden:

1. `--variable` en la CLI
2. Variables de entorno
3. `config/local.yaml` (copiar desde `config/local.yaml.example`)
4. Perfil local `data/chrome-profile/Default` si existe; si no, el perfil de Chrome de macOS (solo si macOS permite leerlo)
5. Diálogo interactivo si aún falta la URL

macOS puede bloquear `~/Library/Application Support/Google/Chrome` (TCC). Si aparece `Operation not permitted` sobre `Local State`, ejecuta el robot desde **Terminal.app** o siembra una copia local:

```bash
# En Terminal.app, con Chrome cerrado
./scripts/seed_chrome_profile.sh
```

```bash
cp config/local.yaml.example config/local.yaml
# editar wishlist_url en config/local.yaml

robot --outputdir results tasks/amazon/wishlist_amazon_price_updater.robot
```

### Ejecución Básica (Entorno por defecto: `dev`)
```bash
robot --outputdir results tasks/main_process.robot

# Ejecución directa de la tarea de actualización de notas de Amazon
robot --outputdir results tasks/amazon/wishlist_amazon_price_updater.robot

# Ejecución del ejemplo de navegación de Insumos Cerveceros
robot --outputdir results tasks/insumoscerveceros/insumoscerveceros_sample.robot
```

### Ejecución Seleccionando Entorno (`uat` o `prod`)
```bash
robot --outputdir results --variable ENV:prod tasks/main_process.robot
```

### Ejecución con Reintentos de Transacciones Fallidas
```bash
robot --outputdir results --rerunfailed results/output.xml tasks/main_process.robot
```

### Ejecución en Paralelo (con `pabot`)
```bash
pabot --processes 2 --outputdir results tasks/
```

---

## 🛡️ Principios Arquitectónicos Clave

1. **Separación por sitio y responsabilidad:** 
   - Las tareas se agrupan por portal en `tasks/<sitio>/`.
   - La lógica y métricas exclusivas de un portal se mantienen en `keywords/<sitio>/`.
   - Las interacciones técnicas reutilizables residen en `keywords/common/system/`.
2. **Localizadores aislados por portal:**
   - Los selectores específicos se almacenan en `resources/<sitio>/locators.yaml`.
   - Los recursos genéricos o legados se mantienen en `resources/common/`.
3. **Manejo Dual de Excepciones:**
   - **Excepciones de Negocio:** Errores esperados por datos inválidos. Se registran sin frenar el flujo.
   - **Excepciones de Sistema:** Caídas de servicio, timeouts, etc. Disparan capturas de pantalla de evidencia y políticas de reintento.
4. **Métricas y Visibilidad de Operación:**
   - El robot contabiliza transacciones procesadas, exitosas y excepciones de cada tipo, emitiendo un resumen consolidador en consola y logs.

---

## 🔍 Calidad de Código y Estilo

El proyecto incluye soporte para linters y formateadores automáticos:

```bash
# Analizar calidad de código con Robocop
robocop .

# Formatear archivos con Robotidy
robotidy .
```

---

## 📋 Trazabilidad de Defectos para Desarrollo (@Agent: Ralph_Developer)
Cuando el equipo de calidad detecte no conformidades, consulte la plantilla en [`docs/QA_DEFECT_TEMPLATE.md`](docs/QA_DEFECT_TEMPLATE.md) para generar un informe detallado con causa raíz y contexto para su corrección inmediata.
