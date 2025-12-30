#!/usr/bin/env python3
"""Pipeline orquestador para validación de delitos."""

import os
import sys
from pathlib import Path
import importlib.util

# Configurar encoding en Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Agregar directorio raíz al path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.config.config_manager import config
from src.utils import get_project_logger

# Configurar logger
logger = get_project_logger(__name__)


def _load_module(module_path: Path, attr: str = None):
    """Carga un módulo dinámicamente desde una ruta."""
    spec = importlib.util.spec_from_file_location(module_path.stem, str(module_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, attr) if attr else module


def run_pipeline(dataset_name: str, api_key: str = None, provider: str = "deepseek"):
    """Ejecuta el pipeline completo de validación."""
    logger.info(f"Iniciando pipeline para dataset: {dataset_name}")
    paths = config.get_dataset_paths(dataset_name)
    scripts_dir = Path(__file__).resolve().parent / "scripts"

    # Cargar módulos
    process_excel = _load_module(scripts_dir / "1_data_processor.py", "process_excel")
    pattern_cleaner_mod = _load_module(scripts_dir / "2_pattern_analyzer_cleaner.py")
    PatternAnalyzerCleaner = getattr(pattern_cleaner_mod, "PatternAnalyzerCleaner")
    run_validation = _load_module(scripts_dir / "4_Api_delito_validador.py", "run_validation")
    mod_lotes = _load_module(scripts_dir / "5_lotes_processor.py")
    ResultProcessor = getattr(mod_lotes, "ResultProcessor")
    error_analyzer_mod = _load_module(scripts_dir / "6_Error_results.py")
    ErrorAnalyzer = getattr(error_analyzer_mod, "ErrorAnalyzer")
    excel_reporter_mod = _load_module(scripts_dir / "7_excel_reporter.py")
    ExcelAnalysisGenerator = getattr(excel_reporter_mod, "ExcelAnalysisGenerator")
    excel_merge_mod = _load_module(scripts_dir / "8_excel_merge.py")
    ExcelMerger = getattr(excel_merge_mod, "ExcelMerger")

    logger.info("Paso 1: Procesando archivo Excel inicial")
    input_excel = paths['raw']
    processed_path = paths['processed']
    reports_dir = paths['reports_dir']
    rejected_path = reports_dir / f"rechazados_{dataset_name}.jsonl"
    
    process_excel(input_excel, processed_path, rejected_path, reports_dir)

    logger.info("Paso 2: Analizando y limpiando patrones")
    pattern_cleaner = PatternAnalyzerCleaner(dataset_name)
    pattern_cleaner.run()

    logger.info("Paso 3: Validando datos con API")
    config.create_dataset_structure(dataset_name)
    validation_completed = run_validation(dataset_name, provider=provider, auto_confirm=False, show_header=True, api_key=api_key)
    
    if not validation_completed:
        logger.warning("Pipeline cancelado por el usuario o error en validación")
        print("\n" + "="*80)
        print("❌ Pipeline cancelado. No se ejecutarán scripts posteriores.")
        print("="*80)
        return

    logger.info("Paso 4: Unificando resultados de lotes")
    lotes_dir = paths['lotes_dir']
    if lotes_dir.exists() and any(lotes_dir.glob("*.jsonl")):
        processor = ResultProcessor(dataset_name)
        processor.process()
    else:
        print(f"No hay lotes en {lotes_dir}. Se omite unificación.")

    logger.info("Paso 5: Analizando errores y casos problemáticos")
    analyzer = ErrorAnalyzer(dataset_name)
    analysis_results = analyzer.run_analysis()
    
    print("\n" + "="*80)
    print("REVISION DE ERRORES COMPLETADA")
    print("="*80)
    print(f"Casos problemáticos encontrados: {analysis_results['problematic_cases']}")
    print(f"Total de registros procesados: {analysis_results['total_records']}")
    
    if analysis_results['problematic_cases'] > 0:
        print(f"\nAdvertencia: Se encontraron {analysis_results['problematic_cases']} casos problemáticos.")
        print("Los archivos de error están guardados en la carpeta 'Errores' del dataset.")

    logger.info("Paso 6: Generando reportes Excel")
    try:
        gen = ExcelAnalysisGenerator(dataset_name)
        gen.generate_excel()
    except Exception as e:
        logger.error(f"Error generando Excel de análisis: {e}")
        print(f"Aviso: no se pudo generar Excel de análisis: {e}")
    
    logger.info("Paso 7: Fusionando resultados con Excel original")
    try:
        merger = ExcelMerger(dataset_name)
        stats = merger.process()
        
        # Validar que se retornaron estadísticas válidas
        if stats and isinstance(stats, dict):
            merger.print_report(stats)
            if 'output_file' in stats:
                print(f"Archivo validado: {stats['output_file']}")
            print()
            logger.info(f"Pipeline completado exitosamente. Archivo final: {stats.get('output_file', 'desconocida')}")
        else:
            logger.error("process() retornó estadísticas inválidas")
            print("Aviso: no se pudo validar las estadísticas de fusión")
    except Exception as e:
        logger.error(f"Error fusionando con Excel original: {e}")
        print(f"Aviso: no se pudo fusionar con Excel original: {e}")


def get_api_key() -> str:
    """Valida y retorna la API key configurada."""
    api_key = config.get_api_key("deepseek")

    if api_key == "sk-tucodigosecretoaquisincomillas":
        print("\n❌ ERROR: API_KEY no está configurada en .env")
        print("   1. Abre el archivo .env en la raíz del proyecto")
        print("   2. Reemplaza el valor placeholder con tu clave real")
        print("   3. Guarda el archivo y vuelve a ejecutar")
        sys.exit(1)

    if not api_key or len(api_key) < 20:
        print("\n❌ ERROR: API_KEY vacía o inválida en .env")
        print("   Las claves de API deben tener al menos 20 caracteres")
        sys.exit(1)

    if not api_key.startswith("sk-"):
        print("\n❌ ERROR: API_KEY tiene formato inválido")
        print("   Las claves deben comenzar con 'sk-'")
        print(f"   Tu clave comienza con: {api_key[:5]}...")
        sys.exit(1)

    import re
    if not re.match(r'^sk-[a-zA-Z0-9\-]+$', api_key):
        print("\n❌ ERROR: API_KEY contiene caracteres inválidos")
        print("   Solo se permiten letras, números y guiones")
        sys.exit(1)

    try:
        from openai import OpenAI
        test_client = OpenAI(api_key=api_key, base_url=config.api.base_url, timeout=5.0)
        test_client.models.list()
        print(f"✓ API Key validada correctamente")
    except Exception as e:
        error_str = str(e).lower()
        if "401" in error_str or "unauthorized" in error_str or "invalid" in error_str:
            print("\n❌ ERROR: API_KEY rechazada por el servidor")
            print("   La clave existe pero no es válida o ha expirado")
            print(f"   Error: {str(e)[:100]}")
            sys.exit(1)
        elif "timeout" in error_str or "connection" in error_str:
            print("⚠️  Advertencia: No se pudo verificar la conexión con el servidor API")
            print("   Continuando con la clave sin verificar...")
        else:
            print(f"⚠️  Advertencia: Error al validar clave: {str(e)[:80]}")
            print("   Continuando de todas formas...")

    return api_key


def get_dataset_interactively() -> str:
    """Obtiene y valida el dataset configurado."""
    current_dataset = config.default_dataset_name
    raw_dir = config.paths.raw_data_dir
    excel_file = raw_dir / f"{current_dataset}.xlsx"
    
    if not excel_file.exists():
        excel_files = list(raw_dir.glob("*.xlsx")) + list(raw_dir.glob("*.xls"))
        
        if not excel_files:
            print(f"\nERROR: No hay archivos Excel en data/raw/")
            sys.exit(1)
        
        print(f"\nERROR: No se encontró '{current_dataset}.xlsx' en data/raw/")
        print(f"\nArchivos disponibles:")
        for i, file in enumerate(sorted(excel_files), 1):
            print(f"   {i}. {file.stem}")
        
        print(f"\nActualiza 'dataset_name' en config.yaml")
        sys.exit(1)
    
    return current_dataset


def main():
    """Punto de entrada principal."""
    print("=" * 80)
    print("PIPELINE DE VALIDACION DE DELITOS")
    print("=" * 80)
    
    api_key = get_api_key()
    dataset_name = get_dataset_interactively()
    
    print("\nIniciando pipeline...\n")
    run_pipeline(dataset_name, api_key)


if __name__ == "__main__":
    main()


