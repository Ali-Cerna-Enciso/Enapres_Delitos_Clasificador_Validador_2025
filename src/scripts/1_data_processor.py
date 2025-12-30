#!/usr/bin/env python3
"""Procesador de datos: Excel a JSONL con limpieza y agrupación"""

import os
import json
import re
import sys
import pandas as pd
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

try:
    from src.config.config_manager import config
    from src.utils import get_project_logger
    logger = get_project_logger(__name__)
except Exception as e:
    print(f"⚠️  Advertencia: No se pudo cargar config: {e}")
    config = None
    logger = None

if config:
    proc_cfg = config.get_processing_config()
    PROCESSING_MODE = proc_cfg.get('mode', 'complex')
    
    if PROCESSING_MODE == "complex":
        ID_COMPONENTS = proc_cfg.get('id_components', ['HOGAR', 'P201', 'ID', 'P424_ID'])
        EXCEL_TEXT_COLUMN = proc_cfg.get('text_column', 'OBS_400A')
        EXCEL_CODE_COLUMN = proc_cfg.get('code_column', 'P400A_COD')
    else:  # simple
        SIMPLE_ID_COLUMN = proc_cfg.get('id_column', 'ID')
        SIMPLE_CODE_COLUMN = proc_cfg.get('code_column', 'CODIGO')
        EXCEL_TEXT_COLUMN = proc_cfg.get('text_column', 'OBSERVACION')
else:
    # Fallback si config no está disponible
    PROCESSING_MODE = "complex"
    ID_COMPONENTS = ['HOGAR', 'P201', 'ID', 'P424_ID']
    EXCEL_TEXT_COLUMN = 'OBS_400A'
    EXCEL_CODE_COLUMN = 'P400A_COD'
    SIMPLE_ID_COLUMN = 'ID'
    SIMPLE_CODE_COLUMN = 'CODIGO'

ID_DELITO_COL = 'ID_DELITO_IA'
ID_BASE_COL = 'ID_BASE'

MIN_OBS_LENGTH = 21
MIN_WORDS = 5

RE_ALPHA_WORDS = re.compile(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+')
PATRON_PALABRAS_CLAVE = re.compile(
    r'\b(P\.?|ITEM|P\_?|PREG\.?|PGR\.?|PRG\.?|CAPÍTULO|ITEN|PGTA|I|ALTERNATIVA)\b', 
    re.IGNORECASE
)
RE_PUNTUACION_INICIAL = re.compile(r'^[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+')




def limpiar_texto_completo(texto: str) -> str:

    if not isinstance(texto, str): 
        return ""
    
    parte_inicial = texto[:60]
    resto_del_texto = texto[60:]
    texto = (re.sub(r'\d', '', parte_inicial) + resto_del_texto).strip()
    
    texto = PATRON_PALABRAS_CLAVE.sub('', texto)
    texto = RE_PUNTUACION_INICIAL.sub('', texto)
    
    return re.sub(r'\s{2,}', ' ', texto).strip()

def process_excel(input_excel_path: Path, output_processed_path: Path, output_rejected_path: Path, reports_dir: Path = None):

    if logger:
        logger.info(f"Iniciando procesamiento de Excel: {input_excel_path.name}")
    
    if reports_dir is None:
        reports_dir = output_rejected_path.parent
    
    # Crear directorios
    output_processed_path.parent.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Actualizar output_rejected_path si no está en reports_dir
    if output_rejected_path.parent != reports_dir:
        output_rejected_path = reports_dir / output_rejected_path.name
    
    # Carga y validación de datos
    try:
        df = pd.read_excel(input_excel_path)
        print(f"1. Datos cargados: {len(df)} registros desde '{Path(input_excel_path).name}'.")
        
        # Validar columnas según modo
        if PROCESSING_MODE == "complex":
            required_cols = ID_COMPONENTS + [EXCEL_TEXT_COLUMN, EXCEL_CODE_COLUMN]
        else:  # simple
            required_cols = [SIMPLE_ID_COLUMN, EXCEL_TEXT_COLUMN, SIMPLE_CODE_COLUMN]
        
        # Filtrar valores None (para columnas opcionales en modo simple)
        required_cols = [col for col in required_cols if col is not None]
        
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"Columnas requeridas no encontradas: {required_cols}")
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Creación de identificadores únicos (solo en modo complex)
    if PROCESSING_MODE == "complex":
        print("\n2. Generando identificadores únicos...")
        for col in ID_COMPONENTS:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64').astype(str)
        
        df[ID_DELITO_COL] = df[ID_COMPONENTS].apply(lambda row: '-'.join(row.replace('<NA>', 'NULO')), axis=1)
        df[ID_BASE_COL] = df[ID_DELITO_COL].str.rsplit('-', n=1).str[0]
        print(f"   -> Columna '{ID_DELITO_COL}' creada. Ejemplo: {df[ID_DELITO_COL].iloc[0]}")
        print(f"   -> Columna '{ID_BASE_COL}' creada. Ejemplo: {df[ID_BASE_COL].iloc[0]}")
    else:  # simple
        print("\n2. Usando ID directo (modo simple)...")
        df[ID_DELITO_COL] = df[SIMPLE_ID_COLUMN].astype(str)
        df[ID_BASE_COL] = df[SIMPLE_ID_COLUMN].astype(str)
        print(f"   -> ID_DELITO_IA = {SIMPLE_ID_COLUMN} (directo)")
        print(f"   -> ID_BASE = {SIMPLE_ID_COLUMN} (sin agrupar)")
    
    # Limpieza y filtrado
    print("\n3. Aplicando limpieza y filtros de calidad...")
    df['observacion_limpia'] = df[EXCEL_TEXT_COLUMN].fillna('').astype(str).apply(limpiar_texto_completo)
    
    mask_validos = (df['observacion_limpia'].str.len() >= MIN_OBS_LENGTH) & \
                   (df['observacion_limpia'].str.count(RE_ALPHA_WORDS) >= MIN_WORDS)
    
    df_limpio = df[mask_validos].copy()
    df_rechazados = df[~mask_validos]
    
    print(f"   -> Registros válidos: {len(df_limpio)}")
    
    # Guardado de registros rechazados
    if not df_rechazados.empty:
        with open(output_rejected_path, 'w', encoding='utf-8') as f:
            for _, row in df_rechazados.iterrows():
                rejected_record = {
                    "id_delito_ia": row[ID_DELITO_COL],
                    "observacion_original": row[EXCEL_TEXT_COLUMN],
                    "observacion_limpia": row['observacion_limpia']
                }
                f.write(json.dumps(rejected_record, ensure_ascii=False) + '\n')
        print(f"   -> Registros rechazados guardados: {len(df_rechazados)} en '{Path(output_rejected_path).name}'")

    # Agrupación por ID_BASE y observación (solo en modo complex)
    print("\n4. Preparando registros para API...")
    
    if PROCESSING_MODE == "complex":
        print("   Agrupando registros por observación única...")
        df_agrupado = (
            df_limpio
            .groupby([ID_BASE_COL, 'observacion_limpia'])
            .agg(
                codigos_delito=(EXCEL_CODE_COLUMN, lambda s: sorted(pd.to_numeric(s, errors='coerce').dropna().astype(int).astype(str).unique())),
                ids_delito_originales=(ID_DELITO_COL, lambda s: sorted(list(s.unique())))
            )
            .reset_index()
        )
        print(f"   -> Registros agrupados: {len(df_limpio)} → {len(df_agrupado)} observaciones únicas")
    else:  # simple - sin agrupar
        print("   Sin agrupación (modo simple, ID único por fila)...")
        # Seleccionar columnas, filtrando None para columnas opcionales
        cols_to_select = [ID_BASE_COL, 'observacion_limpia', ID_DELITO_COL]
        if SIMPLE_CODE_COLUMN is not None:
            cols_to_select.append(SIMPLE_CODE_COLUMN)
        
        df_agrupado = df_limpio[cols_to_select].copy()
        
        # Procesar códigos si existe la columna
        if SIMPLE_CODE_COLUMN is not None:
            df_agrupado['codigos_delito'] = df_agrupado[SIMPLE_CODE_COLUMN].apply(
                lambda x: [str(int(x))] if pd.notna(x) else []
            )
        else:
            df_agrupado['codigos_delito'] = df_agrupado.apply(lambda row: [], axis=1)  # Lista vacía por fila
        
        df_agrupado['ids_delito_originales'] = df_agrupado[ID_DELITO_COL].apply(lambda x: [x])
        df_agrupado = df_agrupado[[ID_BASE_COL, 'observacion_limpia', 'codigos_delito', 'ids_delito_originales']]
        print(f"   -> Registros procesados: {len(df_agrupado)} (sin cambios, 1:1)")

    # Reporte de agrupación
    print("\n" + "-" * 50)
    print(" REPORTE DE AGRUPACIÓN")
    print("-" * 50)
    
    filas_antes = len(df_limpio)
    filas_despues = len(df_agrupado)
    
    if filas_antes > 0:
        reduccion_pct = (1 - filas_despues / filas_antes) * 100
        print(f"Registros procesados: {filas_antes} → {filas_despues}")
        print(f"Reducción: {filas_antes - filas_despues} registros ({reduccion_pct:.2f}%)")
    
    # Verificación de consistencia
    obs_unicas_por_id_base = df_limpio.groupby(ID_BASE_COL)['observacion_limpia'].nunique()
    ids_inconsistentes = obs_unicas_por_id_base[obs_unicas_por_id_base > 1]
    
    if ids_inconsistentes.empty:
        print("Verificación: Consistencia de observaciones confirmada")
    else:
        print(f"Advertencia: {len(ids_inconsistentes)} ID_BASE con observaciones inconsistentes")
        print(f"Ejemplos: {list(ids_inconsistentes.head(3).index)}")
    
    # Ejemplo de agrupación
    conteo_ids = df_limpio[ID_BASE_COL].value_counts()
    if filas_antes > filas_despues and not conteo_ids[conteo_ids > 1].empty:
        print("\nEjemplo de agrupación:")
        id_ejemplo = conteo_ids[conteo_ids > 1].index[0]
        print(f"ID_BASE: {id_ejemplo}")
        
        df_antes = df_limpio[df_limpio[ID_BASE_COL] == id_ejemplo]
        print("\nAntes del agrupamiento:")
        print(df_antes[[ID_DELITO_COL, EXCEL_CODE_COLUMN, 'observacion_limpia']].to_string(index=False))
        
        df_despues = df_agrupado[df_agrupado[ID_BASE_COL] == id_ejemplo]
        print("\nDespués del agrupamiento:")
        print(df_despues[[ID_BASE_COL, 'codigos_delito', 'ids_delito_originales', 'observacion_limpia']].to_string(index=False))
    
    print("-" * 50)

    # Guardado del dataset final
    print("\n5. Generando archivo de salida...")
    
    with open(output_processed_path, 'w', encoding='utf-8') as f:
        for _, row in df_agrupado.iterrows():
            assistant_content = {
                "codigos_delito": row['codigos_delito'],
                "ids_delito_originales": row['ids_delito_originales']
            }
            json_line = {
                "id": row[ID_BASE_COL],
                "messages": [
                    {"role": "system", "content": "P0P"},
                    {"role": "user", "content": row['observacion_limpia']},
                    {"role": "assistant", "content": json.dumps(assistant_content, ensure_ascii=False)}
                ]
            }
            f.write(json.dumps(json_line, ensure_ascii=False) + '\n')
    
    print(f"   -> Dataset procesado guardado: '{Path(output_processed_path).name}'")
    print(f"\nProcesamiento completado. Registros finales: {len(df_agrupado)}")
    
    if logger:
        logger.info(f"Procesamiento completado: {len(df_agrupado)} registros procesados, {len(df_rechazados)} rechazados")

def main(dataset_name: str = None):
    """Permite ejecución directa o desde orquestador"""
    if dataset_name is None:
        if config is None:
            print(" ERROR: No se pudo cargar config_manager")
            print("   Asegúrate de ejecutar desde la raíz del proyecto")
            sys.exit(1)
        dataset_name = os.getenv('DATASET_NAME', config.default_dataset_name)
    
    paths = config.get_dataset_paths(dataset_name)
    input_excel = paths['raw']
    processed_path = paths['processed']
    reports_dir = paths['reports_dir']
    rejected_path = reports_dir / f"rechazados_{dataset_name}.jsonl"
    
    # Mostrar configuración
    print("=" * 80)
    print(" Dataset a procesar:", dataset_name)
    print(" Excel de entrada:", input_excel)
    print(" Existe:", "SÍ" if input_excel.exists() else "NO")
    print("=" * 80)
    print()
    
    process_excel(input_excel, processed_path, rejected_path, reports_dir)

if __name__ == "__main__":
    main()