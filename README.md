# Enapres-delitos-validator

Sistema modular de validación de consistencia entre respuestas categóricas y narrativas de texto libre para encuestas nacionales de seguridad ciudadana. Desarrollado como herramienta de apoyo para analistas de datos estadísticos del sector público.

---

## 📋 Descripción del Proyecto

Este proyecto implementa un pipeline completo y modular para procesar, limpiar y validar observaciones de delitos. El sistema utiliza análisis de patrones, limpieza automatizada, validación vía API y unificación de resultados.

### ⚠️ Propósito y Alcance

**Este sistema es una herramienta de PRE-PROCESAMIENTO de información:**

- ✅ **Facilita la interpretación** de datos mediante limpieza automatizada y análisis de patrones
- ✅ **Filtra observaciones** que no cumplen requisitos mínimos de calidad (longitud, palabras, claridad)
- ✅ **Asiste en la validación** mediante IA, identificando posibles inconsistencias
- ✅ **Genera reportes** con justificaciones para revisión humana

**IMPORTANTE: Este sistema NO toma decisiones finales**
- ❌ No reemplaza el criterio humano del analista
- ❌ No determina conclusiones definitivas sobre los datos
- ✅ **Es una herramienta de apoyo** que requiere revisión y validación manual de resultados
- ✅ Los archivos finales deben ser **revisados por personal capacitado** antes de tomar decisiones

---

## 🏗️ Estructura del Proyecto

```
Enapres-delitos-validator/
│
├── 📁 src/                              # Código fuente principal
│   ├── 📁 config/                       # ⚙️ Configuración centralizada
│   │   └── config_manager.py            # Gestor de configuración y rutas 
│   │
│   ├── 📁 prompts/                      # 📚 Base de conocimiento (no incluida en repositorio)
│   │   └── crime_validation_prompts.py  # Definiciones de delitos y plantillas
│   │
│   ├── 📁 scripts/                      # 🔄 Pipeline de procesamiento (7 pasos)
│   │   ├── 1_data_processor.py          # Procesa Excel, limpia y valida
│   │   ├── 2_pattern_analyzer_cleaner.py    # Analiza patrones y limpia observaciones
│   │   ├── 4_Api_delito_validador.py    # Envía a API en lotes
│   │   ├── 5_lotes_processor.py         # Unifica resultados de lotes
│   │   ├── 6_Error_results.py           # Analiza errores detectados
│   │   ├── 7_excel_reporter.py          # Genera reporte Excel
│   │   └── 8_excel_merge.py             # Fusiona con archivo original
│   │
│   ├── 📁 validation/                   # 🧪 Herramientas de validación
   │   ├── Test_Api.py                  # Validador de API con análisis de consitencia
│   │  └── ver_prompt.py                # Documenta flujo entrada/salida
│   │   
│   │
│   └── main.py                          # 🎯 Orquestador del pipeline
│
├── 📁 data/                             # 💾 Datos del proyecto
│   ├── 📁 raw/                          # 📥 Datos originales (Excel)
│   ├── 📁 processed/                    # 🔧 Archivos procesados
│   │   ├── 📁 reports/                  # Registros rechazados
│   │   └── 📁 utils/                    # Patrones de limpieza detectados
│   └── 📁 results/                      # ✅ Resultados por dataset
│       └── [dataset]/
│           ├── 📁 Lotes/                # Resultados de API por lote
│           ├── 📁 Errores/              # Casos problemáticos identificados
│           ├── anidado_*.jsonl          # Resultados en formato anidado
│           ├── desanidado_*.jsonl       # Resultados en formato desanidado
│           ├── analisis_*.xlsx          # Reporte de análisis
│           └── validado_*.xlsx          # 🎁 ARCHIVO FINAL FUSIONADO
│
├── 📄 config.yaml                       # ⚙️ Configuración del proyecto
├── 📄 requirements.txt                  # 📦 Dependencias Python
├── 📄 prompt_completo.txt               # 📋 Documentación de prompts (generado)
└── 📄 README.md                         # 📖 Este archivo
```

## 🚀 Guía de Ejecución Rápida

### Paso 1: Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 2: Configurar la API Key

```powershell
# Windows (PowerShell)
$env:API_KEY="tu_clave_secreta_aqui"

# Verificar
echo $env:API_KEY
```

### Paso 3: Preparar el archivo Excel

Coloca tu archivo Excel en la carpeta `data/raw/`:

```
data/raw/
└── <nombre_de_tu_dataset>.xlsx    ← Con extensión .xlsx
```

### Paso 4: Configurar el dataset

Edita `config.yaml` para especificar el dataset a procesar:

```yaml
dataset_name: "<nombre_de_tu_dataset>"    # Sin .xlsx - solo el nombre base
```

**Importante**: 
- En `config.yaml`: usa **solo el nombre** sin la extensión `.xlsx`
- En `data/raw/`: el archivo debe tener **la extensión `.xlsx`**
- El nombre debe coincidir exactamente (respeta mayúsculas y caracteres especiales)

**Ejemplo**:
- Archivo Excel: `data/raw/Delitos_Octubre.xlsx`
- En config.yaml: `dataset_name: "Delitos_Octubre"`

### Paso 5: Ejecutar el Pipeline Completo

```powershell
python -m src.main
```

El sistema procesará automáticamente todos los pasos del pipeline.

---

## 🔧 Configuración

### config.yaml

```yaml
# Dataset a procesar (sin extensión .xlsx)
dataset_name: "Base_excel_ejemplo"

# Configuración de API
api:
  model_name: "model-name"              # Nombre del modelo a usar
  base_url: "https://api.provider.com/v1" # URL base del proveedor
  temperature: 0.1
  max_tokens: 1000
  top_p: 0.9
  timeout: 90
  max_retries: 3
  retry_delay: 60

# Parámetros de procesamiento
processing:
  batch_size: 350               # Tamaño de lote para API
  memory_cleanup_every: 5       # Limpieza de memoria cada N lotes
  pattern_min_count: 10         # Mínimo de repeticiones para eliminar patrón
  pattern_min_percent: 5.0      # Mínimo porcentaje para eliminar patrón (%)
```

### Variables de Entorno

```bash
# Requerida para proveedor de API
export API_KEY="tu_clave_api_aqui"

# Opcional: sobrescribe config.yaml
export DATASET_NAME="<nombre_de_tu_dataset>"
```

**Jerarquía de configuración:**
1. Variable de entorno `DATASET_NAME` (mayor prioridad)
2. Archivo `config.yaml`
3. Valores por defecto en el código

---

## 🎯 Resultado Final

Al finalizar el pipeline, encontrarás el archivo validado en:

```
data/results/<dataset>/validado_<dataset>.xlsx
```

Este archivo contiene:
- Todos los registros del Excel original
- Columnas adicionales con resultados de validación
- Formato condicional para facilitar revisión
- Métricas de coincidencia (MATCH_DELITO)
- Justificaciones y detalles de errores

---

## 📋 Requisitos Previos

1. **Archivo Excel** en `data/raw/<dataset>.xlsx` con columnas: HOGAR, P201, ID, P424_ID, OBS_400A
2. **API Key** configurada: `$env:API_KEY="sk-xxxxx"`
3. **config.yaml** con nombre del dataset
4. **Dependencias**: `pip install -r requirements.txt`

---

##  Flujo de Datos - Visualización Completa

```
┌──────────────────────────────────────────────────────────────┐
│            ENTRADA: data/raw/dataset.xlsx                    │
│   (HOGAR, P201, ID, P424_ID, OBS_400A)                       │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
          ┌────────────────────────────┐
          │ 1️⃣ data_processor.py       │
          │ Limpia y valida            │
          │ Datos de Excel             │
          └──────┬─────────────┬────────┘
                 │             │
          ┌──────▼────┐   ┌────▼──────┐
          │ procesado  │   │ rechazados │
          │ *.jsonl ✅ │   │ *.jsonl ❌ │
          └──────┬────┘   └────────────┘
                 │
                 ▼
          ┌────────────────────────────┐
          │ 2️⃣ pattern_analyzer_cleaner│
          │ Detecta y elimina          │
          │ patrones redundantes       │
          └──────┬─────────────────────┘
                 │
                 ▼
          Sprocesado_*.jsonl
                 │
                 ▼
          ┌────────────────────────────┐
          │ 4️⃣ Api_delito_validador    │
          │ Valida con IA/API          │
          │ en lotes (batch_size: 350) │
          └──────┬─────────────────────┘
                 │
                 ▼
          ┌────────────────────────────┐
          │ Resultados por Lotes       │
          │ (Lote 1, 2, 3, ...)        │
          └──────┬─────────────────────┘
                 │
                 ▼
          ┌────────────────────────────┐
          │ 5️⃣ lotes_processor         │
          │ Unifica todos los lotes    │
          │ en archivos JSONL          │
          └──────┬──────────────┬──────┘
                 │              │
          ┌──────▼────┐   ┌─────▼─────┐
          │ anidado    │   │ desanidado │
          │ *.jsonl    │   │ *.jsonl    │
          └──────┬────┘   └─────┬──────┘
                 │              │
          ┌──────┴──────┐       │
          │             │       │
          ▼             ▼       │
     ┌─────────┐  ┌──────────┐ │
     │ 6️⃣      │  │ 7️⃣       │ │
     │ Error   │  │ Excel    │ │
     │ results │  │ reporter │ │
     └────┬────┘  └────┬─────┘ │
          │            │       │
          ▼            ▼       │
    Errores/    analisis_     │
    *.jsonl     *.xlsx        │
                      │       │
                 ┌────┴───────┘
                 │
                 ▼
          ┌────────────────────────────┐
          │ 8️⃣ excel_merge             │
          │ Fusiona con Excel original │
          │ + Formato condicional      │
          └──────┬─────────────────────┘
                 │
                 ▼
          ┌────────────────────────────┐
          │ ✨ SALIDA FINAL            │
          │ validado_*.xlsx            │
          │ (Listo para revisar)       │
          └────────────────────────────┘
```

---

## 🔐 Seguridad y Privacidad

- ✅ La API Key nunca se guarda en archivos (solo en variable de entorno)
- ✅ Los datos se envían al proveedor de API externo (verificar políticas de privacidad)
- ✅ Se recomienda usar credenciales de prueba antes de procesar datos sensibles
- ✅ Los resultados se guardan localmente en tu máquina
- ⚠️ No compartas archivos con API_KEY configurada
- ⚠️ Los prompts no se incluyen en el repositorio (lógica de negocio propietaria)

---

## 📞 Soporte y Contacto

Para reportar problemas o sugerencias:
1. Verifica que completaste el ✅ Checklist Previo a la Ejecución
2. Ejecuta `python src/validation/Test_Api.py` para verificar conectividad y consistencia
3. Revisa `prompt_completo.txt` para entender el flujo

---

## � Autor

Desarrollado por **Ali Cerna Enciso**, analista de datos especializado en seguridad ciudadana y procesamiento de encuestas.

- GitHub: [@Ali-Cerna-Enciso](https://github.com/Ali-Cerna-Enciso)

---

## �📄 Licencia

Ver archivo [LICENSE](LICENSE)


