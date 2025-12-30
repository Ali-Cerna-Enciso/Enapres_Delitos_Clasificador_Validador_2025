#!/usr/bin/env python3
"""
Gestor de Configuración Centralizado
Jerarquía de carga:
1. Variables de entorno (desde .env o sistema)
2. Archivo config.yaml (si existe y PyYAML instalado)
3. Valores por defecto en este archivo (fallback)
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# Cargar variables de entorno desde .env si existe
if load_dotenv:
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)  # override=True fuerza actualización
    else:
        load_dotenv(override=True)  # Fallback a búsqueda automática


# ============================================================================
# VALORES POR DEFECTO (FALLBACK)
# ============================================================================
# Estos valores solo se usan si config.yaml no existe o no se puede leer

@dataclass
class APIConfig:
    """Configuración de API (fallback si config.yaml no está disponible)"""
    model_name: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com/v1"
    temperature: float = 0.2         # Fallback conservador (vs 0.1 en YAML)
    max_tokens: int = 512              # Fallback bajo (vs 1000 en YAML)
    top_p: float = 0.95                # Fallback conservador (vs 0.9 en YAML)
    timeout: int = 30                  # Fallback bajo (vs 90 en YAML)
    max_retries: int = 1               # Fallback bajo (vs 3 en YAML)
    retry_delay: int = 30              # Fallback bajo (vs 60 en YAML)


@dataclass
class ProcessingConfig:
    """Configuración de procesamiento (fallback si config.yaml no está disponible)"""
    save_every: int = 10               # Fallback bajo (guardar más frecuente)
    batch_size: int = 100              # Fallback bajo (vs 350 en YAML)
    memory_cleanup_every: int = 2      # Fallback más frecuente (vs 5 en YAML)
    pattern_min_count: int = 5         # Fallback bajo (vs 10 en YAML)
    pattern_min_percent: float = 2.0   # Fallback bajo (vs 5.0 en YAML)


@dataclass
class DataProcessingConfig:
    """Configuración de modo de procesamiento (COMPLEX vs SIMPLE)"""
    mode: str = "complex"              # "complex" o "simple"
    
    # COMPLEX mode
    complex_id_components: list = None
    complex_text_column: str = "OBS_400A"
    complex_code_column: str = "P400A_COD"
    
    # SIMPLE mode
    simple_id_column: str = "ID"
    simple_code_column: str = "CODIGO"
    simple_text_column: str = "OBSERVACION"
    
    def __post_init__(self):
        if self.complex_id_components is None:
            self.complex_id_components = ["HOGAR", "P201", "ID", "P424_ID"]

@dataclass
class PromptsConfig:
    """Configuración de prompts - Selección de versión"""
    version: str = "1"                 # Versión de prompts: "1" o "2"


@dataclass
class PathConfig:
    """Rutas del proyecto"""
    project_root: Path
    data_dir: Path
    raw_data_dir: Path
    processed_data_dir: Path
    results_dir: Path

    def __post_init__(self):
        for path_attr in [
            'data_dir', 'raw_data_dir', 'processed_data_dir',
            'results_dir'
        ]:
            path = getattr(self, path_attr)
            path.mkdir(parents=True, exist_ok=True)


# ============================================================================
# GESTOR DE CONFIGURACIÓN
# ============================================================================

class ConfigManager:
    
    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parents[2]
        
        # Inicializar rutas
        self.paths = PathConfig(
            project_root=project_root,
            data_dir=project_root / "data",
            raw_data_dir=project_root / "data" / "raw",
            processed_data_dir=project_root / "data" / "processed",
            results_dir=project_root / "data" / "results",
        )
        
        # Inicializar configuraciones con valores por defecto
        self.api = APIConfig()
        self.processing = ProcessingConfig()
        self.data_processing = DataProcessingConfig()
        self.prompts = PromptsConfig()
        
        # Dataset por defecto (fallback final)
        self.default_dataset_name = os.getenv("DATASET_NAME", "Datos_Mayo(2)")
        
        # Cargar y sobrescribir desde config.yaml (si existe)
        self._load_yaml_config(project_root / "config.yaml")

    def _load_yaml_config(self, yaml_path: Path):
        """Carga configuración desde config.yaml y sobrescribe valores por defecto"""
        
        if yaml is None:
            print("⚠️  ADVERTENCIA: PyYAML no instalado. Ejecuta: pip install PyYAML")
            print("   Usando configuración por defecto.")
            return
        
        if not yaml_path.exists():
            print(f"⚠️  ADVERTENCIA: No se encontró {yaml_path}")
            print("   Usando configuración por defecto.")
            return
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            # Sobrescribir dataset_name
            if 'dataset_name' in data:
                self.default_dataset_name = str(data['dataset_name'])
            
            # Sobrescribir configuración de API
            api_cfg = data.get('api', {})
            for k, v in api_cfg.items():
                if hasattr(self.api, k):
                    setattr(self.api, k, v)
            
            # Sobrescribir configuración de procesamiento
            proc_cfg = data.get('processing', {})
            for k, v in proc_cfg.items():
                if hasattr(self.processing, k):
                    setattr(self.processing, k, v)
            
            # Sobrescribir configuración de data processing (COMPLEX/SIMPLE)
            dp_cfg = data.get('data_processing', {})
            if 'mode' in dp_cfg:
                self.data_processing.mode = dp_cfg['mode']
            
            if 'complex' in dp_cfg:
                complex_cfg = dp_cfg['complex']
                if 'id_components' in complex_cfg:
                    self.data_processing.complex_id_components = complex_cfg['id_components']
                if 'excel_text_column' in complex_cfg:
                    self.data_processing.complex_text_column = complex_cfg['excel_text_column']
                if 'excel_code_column' in complex_cfg:
                    self.data_processing.complex_code_column = complex_cfg['excel_code_column']
            
            if 'simple' in dp_cfg:
                simple_cfg = dp_cfg['simple']
                if 'id_column' in simple_cfg:
                    self.data_processing.simple_id_column = simple_cfg['id_column']
                if 'code_column' in simple_cfg:
                    self.data_processing.simple_code_column = simple_cfg['code_column']
                if 'text_column' in simple_cfg:
                    self.data_processing.simple_text_column = simple_cfg['text_column']
            
            # Sobrescribir configuración de prompts
            prompts_cfg = data.get('prompts', {})
            if 'version' in prompts_cfg:
                self.prompts.version = str(prompts_cfg['version'])
        
        except Exception as e:
            print(f"❌ ERROR leyendo config.yaml: {e}")
            print("   Usando configuración por defecto.")
            import traceback
            traceback.print_exc()
    
    
    # ========================================================================
    # MÉTODOS DE API
    # ========================================================================
    def get_api_key(self, provider: str = "deepseek") -> str:
        env_var = f"{provider.upper()}_API_KEY"
        api_key = os.getenv(env_var)
        if api_key:
            return api_key
        try:
            from kaggle_secrets import UserSecretsClient  # type: ignore
            user_secrets = UserSecretsClient()
            api_key = user_secrets.get_secret(provider.upper())
            if api_key:
                return api_key
        except Exception:
            pass
        
        # Mensaje de error detallado
        env_file = Path(__file__).resolve().parents[2] / ".env"
        raise ValueError(
            f"\n❌ ERROR: No se encontró {env_var}\n"
            f"   Buscó en: {env_file}\n"
            f"   Asegúrate de que existe el archivo .env en la raíz del proyecto\n"
            f"   y que contiene: {env_var}=tu_clave_aqui"
        )

    def setup_api_client(self, provider: str = "deepseek"):
        import openai  # lazy import
        api_key = self.get_api_key(provider)
        if provider == "deepseek":
            client = openai.OpenAI(api_key=api_key, base_url=self.api.base_url)
        elif provider == "openai":
            client = openai.OpenAI(api_key=api_key)
        else:
            raise ValueError(f"Proveedor no soportado: {provider}")
        return client

    # ========================================================================
    # MÉTODOS DE RUTAS
    # ========================================================================
    
    def get_dataset_paths(self, dataset_name: str) -> Dict[str, Path]:
        """Retorna todas las rutas relacionadas con un dataset específico"""
        dataset_processed_dir = self.paths.processed_data_dir / dataset_name

        return {
            'raw': self.paths.raw_data_dir / f"{dataset_name}.xlsx",
            'dataset_dir': dataset_processed_dir,
            'processed': dataset_processed_dir / f"procesado_{dataset_name}.jsonl",
            'clean': dataset_processed_dir / f"Sprocesado_{dataset_name}.jsonl",
            'reports_dir': dataset_processed_dir / "reports",
            'results_dir': self.paths.results_dir / f"{dataset_name}",
            'lotes_dir': self.paths.results_dir / f"{dataset_name}" / "Lotes",
            'anidado': self.paths.results_dir / f"{dataset_name}" / f"anidado_{dataset_name}.jsonl",
            'desanidado': self.paths.results_dir / f"{dataset_name}" / f"desanidado_{dataset_name}.jsonl",
            'errores_dir': self.paths.results_dir / f"{dataset_name}" / "Errores",
        }

    def validate_dataset_paths(self, dataset_name: str) -> Dict[str, bool]:
        """
        Valida rutas y permisos para un dataset

        Returns:
            Dict con resultados de validación
        """
        import os
        import stat

        paths = self.get_dataset_paths(dataset_name)
        validation_results = {}

        # Validar archivo raw
        raw_path = paths['raw']
        if not raw_path.exists():
            validation_results['raw_exists'] = False
            validation_results['raw_error'] = f"Archivo no encontrado: {raw_path}"
        else:
            validation_results['raw_exists'] = True
            # Verificar permisos de lectura
            if not os.access(raw_path, os.R_OK):
                validation_results['raw_readable'] = False
                validation_results['raw_error'] = "Sin permisos de lectura"
            else:
                validation_results['raw_readable'] = True
                # Verificar tamaño
                size_mb = raw_path.stat().st_size / (1024 * 1024)
                validation_results['raw_size_mb'] = round(size_mb, 2)

        # Validar directorios de escritura
        write_dirs = ['dataset_dir', 'reports_dir', 'results_dir', 'lotes_dir', 'errores_dir']
        for dir_key in write_dirs:
            dir_path = paths[dir_key]
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                # Verificar permisos de escritura
                if not os.access(dir_path, os.W_OK):
                    validation_results[f'{dir_key}_writable'] = False
                    validation_results[f'{dir_key}_error'] = "Sin permisos de escritura"
                else:
                    validation_results[f'{dir_key}_writable'] = True
            except Exception as e:
                validation_results[f'{dir_key}_writable'] = False
                validation_results[f'{dir_key}_error'] = str(e)

        # Verificar espacio en disco
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.paths.project_root)
            free_gb = free / (1024 ** 3)
            validation_results['disk_space_free_gb'] = round(free_gb, 2)
            validation_results['disk_space_sufficient'] = free_gb > 1.0  # Al menos 1GB libre
        except Exception as e:
            validation_results['disk_space_error'] = str(e)

        return validation_results

    def print_dataset_validation(self, dataset_name: str) -> bool:
        """
        Imprime resultados de validación de dataset

        Returns:
            True si todas las validaciones pasaron
        """
        results = self.validate_dataset_paths(dataset_name)

        print("\n" + "="*80)
        print("VALIDACIÓN DE DATASET")
        print("="*80)
        print(f"\nDataset: {dataset_name}")

        all_valid = True

        # Archivo raw
        print(f"\n📄 Archivo de entrada:")
        if results.get('raw_exists'):
            print(f"   ✓ Existe")
            if results.get('raw_readable'):
                print(f"   ✓ Legible ({results.get('raw_size_mb', 0)} MB)")
            else:
                print(f"   ❌ {results.get('raw_error', 'No legible')}")
                all_valid = False
        else:
            print(f"   ❌ {results.get('raw_error', 'No encontrado')}")
            all_valid = False

        # Directorios
        print(f"\n📁 Directorios de salida:")
        write_dirs = ['dataset_dir', 'reports_dir', 'results_dir', 'lotes_dir', 'errores_dir']
        for dir_key in write_dirs:
            if results.get(f'{dir_key}_writable'):
                print(f"   ✓ {dir_key}")
            else:
                error_msg = results.get(f'{dir_key}_error', 'No escribible')
                print(f"   ❌ {dir_key}: {error_msg}")
                all_valid = False

        # Espacio en disco
        print(f"\n💾 Espacio en disco:")
        if 'disk_space_free_gb' in results:
            free_gb = results['disk_space_free_gb']
            sufficient = results.get('disk_space_sufficient', False)
            status = "✓" if sufficient else "⚠️"
            print(f"   {status} Espacio libre: {free_gb} GB")
            if not sufficient:
                print(f"      Advertencia: Se recomienda al menos 1 GB libre")
        else:
            print(f"   ⚠️  No se pudo verificar: {results.get('disk_space_error', 'Unknown')}")

        print("="*80)

        return all_valid

    def create_dataset_structure(self, dataset_name: str):
        paths = self.get_dataset_paths(dataset_name)
        paths['dataset_dir'].mkdir(parents=True, exist_ok=True)
        paths['reports_dir'].mkdir(parents=True, exist_ok=True)
        paths['results_dir'].mkdir(parents=True, exist_ok=True)
        paths['lotes_dir'].mkdir(parents=True, exist_ok=True)
        paths['errores_dir'].mkdir(parents=True, exist_ok=True)
        return paths
    
    # ========================================================================
    # MÉTODOS DE CONFIGURACIÓN DE PROCESAMIENTO DE DATOS
    # ========================================================================
    
    def get_processing_mode(self) -> str:
        """Retorna el modo de procesamiento: 'complex' o 'simple'"""
        return self.data_processing.mode
    
    def get_prompts_version(self) -> str:
        """Retorna la versión de prompts a usar: '1' o '2'"""
        return self.prompts.version
    
    def get_processing_config(self) -> dict:
        """Retorna la configuración completa según el modo actual"""
        mode = self.data_processing.mode
        
        config_dict = {
            'mode': mode,
            'processing_mode': mode  # Para compatibilidad con scripts existentes
        }
        
        if mode == "complex":
            config_dict.update({
                'id_components': self.data_processing.complex_id_components,
                'text_column': self.data_processing.complex_text_column,
                'code_column': self.data_processing.complex_code_column,
            })
        else:  # simple
            config_dict.update({
                'id_column': self.data_processing.simple_id_column,
                'code_column': self.data_processing.simple_code_column,
                'text_column': self.data_processing.simple_text_column,
            })
        
        return config_dict


# ============================================================================
# INSTANCIA GLOBAL
# ============================================================================
# Esta instancia se importa en todos los scripts

config = ConfigManager()
