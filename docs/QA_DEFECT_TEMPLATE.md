# Plantilla de Registro de Defectos (ISTQB Compliant)

> **Uso:** Esta plantilla debe ser completada por el analista de calidad (@Agent: QA-Analyst) al detectar una no conformidad durante la ejecución o pruebas del robot, proporcionando al desarrollador (@Agent: Ralph_Developer) la causa raíz y el contexto exacto del fallo.

---

## ID del Defecto: `DEF-RPA-[AÑO]-[NÚMERO]`
*Ejemplo: DEF-RPA-2026-001*

### 1. Resumen Ejecutivo
- **Título Breve:** *[Ej. Fallo por Timeout al esperar el selector de confirmación de orden]*
- **Módulo / Capa Afectada:** `[tasks | keywords/business | keywords/system | libraries | config]`
- **Severidad:** `[Crítica | Alta | Media | Baja]`
- **Prioridad:** `[P1 - Inmediata | P2 - Alta | P3 - Normal]`
- **Entorno:** `[DEV | UAT | PROD]`
- **Versión / Commit:** `[Git SHA o Tag]`

---

### 2. Clasificación del Fallo
- [ ] **Defecto de Sistema (Técnico):** Falla en el robot, timeout de selector, excepción no capturada, caída de red.
- [ ] **Defecto de Negocio (Regla/Validación):** El robot no valida correctamente un campo obligatorio o procesa un dato inválido.
- [ ] **Defecto de Configuración/Ambiente:** Inconsistencia en `config/*.yaml` o variables de entorno.
- [ ] **Falsa Alarma / Datos de Entrada:** Insumo dañado no contemplado en especificación.

---

### 3. Pre-condiciones
1. Existencia del archivo de insumo en `data/input/`.
2. Conectividad disponible hacia el portal objetivo.
3. Entorno configurado: `ENV=uat`.

---

### 4. Pasos para Reproducir
1. Colocar el archivo de prueba adjunto `data/input/test_case_payload.csv`.
2. Ejecutar el comando:
   ```bash
   robot --outputdir results --variable ENV:dev tasks/main_process.robot
   ```
3. Observar el comportamiento durante el procesamiento del ítem `#1003`.

---

### 5. Resultado Esperado vs. Resultado Actual
- **Resultado Esperado:** 
  *El robot debe atrapar la ausencia del campo 'Legs' como `BUSINESS_EXCEPTION`, registrar la advertencia en el log y continuar con el siguiente ítem sin detener la suite.*
- **Resultado Actual:** 
  *El robot lanza una excepción genérica no controlada `NoSuchElementException` y aborta la ejecución completa del lote.*

---

### 6. Análisis de Causa Raíz (Para @Agent: Ralph_Developer)
- **Archivo donde se localiza el problema:** `[Ej. keywords/business/transaction_processing.resource:L28]`
- **Causa Raíz Identificada:** 
  *Falta la validación previa de integridad de datos antes de disparar la acción UI en el portal. El selector intenta ubicar un componente dinámico con valor vacío.*
- **Recomendación Técnica:**
  *Incorporar la llamada a `DataProcessor.Validate Transaction Data` antes de interactuar con el DOM o condicionar la acción si el valor es nulo.*

---

### 7. Evidencias Adjuntas
- **Log HTML:** `results/log.html`
- **Screenshot del Fallo:** `results/screenshot_fallo_orden_1003.png`
- **Mensaje de Consola:**
  ```text
  WebDriverException: Element not interactable at xpath //input[@placeholder=...]
  ```
