#!/usr/bin/env python3
"""Procesador de lotes: unifica resultados de API y genera formatos anidado/desanidado"""

import os
import json
import glob
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.config.config_manager import config
from src.utils import get_project_logger

logger = get_project_logger(__name__)

# Obtener modo de procesamiento desde config
PROCESSING_MODE = config.get_processing_mode()

class ResultProcessor:

    def __init__(self, dataset_name: str):
        self.dataset_name = dataset_name
        self.dataset_paths = config.get_dataset_paths(dataset_name)
        logger.info(f"Inicializando procesador de lotes para: {dataset_name}")

        # Contadores de errores para tracking
        self.json_decode_errors = 0
        self.general_parse_errors = 0
        self.skipped_no_id = 0

        # Verificar que existen los directorios necesarios
        if not self.dataset_paths['lotes_dir'].exists():
            raise FileNotFoundError(f"No existe directorio de lotes: {self.dataset_paths['lotes_dir']}")

        if not self.dataset_paths['clean'].exists():
            raise FileNotFoundError(f"No existe archivo de referencia: {self.dataset_paths['clean']}")
        
    
    def find_batch_files(self) -> List[Path]:
        # Patrones de búsqueda para archivos de lotes
        patterns = [
            "resultados_lote_*.jsonl",
            "resultados_*_lote_*.jsonl",
            "lote_*.jsonl",
            "batch_*.jsonl"
        ]
        
        batch_files = []
        for pattern in patterns:
            search_path = self.dataset_paths['lotes_dir'] / pattern
            found_files = glob.glob(str(search_path))
            batch_files.extend([Path(f) for f in found_files])
            if found_files:
                break
        
        if not batch_files:
            print(f"ERROR: No se encontraron archivos de lotes en {self.dataset_paths['lotes_dir']}")
            print("Contenido del directorio:")
            if self.dataset_paths['lotes_dir'].exists():
                for file in self.dataset_paths['lotes_dir'].iterdir():
                    print(f"  - {file.name}")
            raise FileNotFoundError("No se encontraron archivos de lotes")
        
        return sorted(batch_files)
    
    def load_batch_files(self) -> Dict[str, Dict]:
        batch_files = self.find_batch_files()
        unified_data = {}
        
        print(f"Unificando {len(batch_files)} archivos de lotes...")
        
        for batch_file in batch_files:
            
            with open(batch_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        record = json.loads(line.strip())
                        
                        # Normalizar ID del registro
                        record_id = None
                        if 'id' in record:
                            record_id = record['id']
                        elif 'case_id' in record:
                            record_id = record.pop('case_id')
                            record['id'] = record_id
                        elif 'id_observacion' in record:
                            record_id = record['id_observacion']
                            record['id'] = record_id
                        
                        if not record_id:
                            self.skipped_no_id += 1
                            print(f"⚠️  Registro sin ID en {batch_file.name}:{line_num}")
                            continue

                        # Si ya existe, sobrescribir con la versión más reciente
                        unified_data[record_id] = record

                    except json.JSONDecodeError as e:
                        self.json_decode_errors += 1
                        print(f"⚠️  Error JSON en {batch_file.name}:{line_num} - {str(e)[:50]}")
                    except Exception as e:
                        self.general_parse_errors += 1
                        print(f"⚠️  Error general en {batch_file.name}:{line_num} - {str(e)[:50]}")
        
        print(f"✅ Registros unificados: {len(unified_data)}")
        if self.json_decode_errors > 0 or self.general_parse_errors > 0 or self.skipped_no_id > 0:
            print(f"⚠️  Errores durante carga de lotes:")
            print(f"   - JSON inválido: {self.json_decode_errors}")
            print(f"   - Errores de parseo: {self.general_parse_errors}")
            print(f"   - Registros sin ID: {self.skipped_no_id}")
        return unified_data
    
    def load_reference_data(self) -> Dict[str, Dict]:
        reference_data = {}
        ref_json_errors = 0
        ref_parse_errors = 0

        with open(self.dataset_paths['clean'], 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line.strip())
                    record_id = record.get('id')

                    if not record_id:
                        print(f"⚠️  Registro sin ID en línea {line_num} del archivo de referencia")
                        continue

                    reference_data[record_id] = record

                except json.JSONDecodeError as e:
                    ref_json_errors += 1
                    print(f"⚠️  Error JSON en referencia línea {line_num} - {str(e)[:50]}")
                except Exception as e:
                    ref_parse_errors += 1
                    print(f"⚠️  Error en referencia línea {line_num} - {str(e)[:50]}")

        if ref_json_errors > 0 or ref_parse_errors > 0:
            print(f"⚠️  Errores en archivo de referencia:")
            print(f"   - JSON inválido: {ref_json_errors}")
            print(f"   - Errores de parseo: {ref_parse_errors}")

        return reference_data
    
    def validate_consistency(self, unified_data: Dict, reference_data: Dict):
        # Validación 1: Conteo total de registros
        unified_count = len(unified_data)
        reference_count = len(reference_data)
        
        if unified_count != reference_count:
            print(f"⚠️  ADVERTENCIA: Desajuste en cantidad total")
            
            # Identificar IDs faltantes o extra
            unified_ids = set(unified_data.keys())
            reference_ids = set(reference_data.keys())
            
            missing_in_unified = reference_ids - unified_ids
            extra_in_unified = unified_ids - reference_ids
            
            if missing_in_unified:
                print(f"   - IDs faltantes en lotes: {len(missing_in_unified)}")
                print(f"     Ejemplos: {sorted(list(missing_in_unified))[:5]}")
            
            if extra_in_unified:
                print(f"   - IDs extra en lotes: {len(extra_in_unified)}")
                print(f"     Ejemplos: {sorted(list(extra_in_unified))[:5]}")
        
        print(f"✅ Validación completada - Lotes: {unified_count} | Referencia: {reference_count}")
    
    def parse_detailed_predictions(self, raw_response: str) -> Dict[str, str]:
        predicted_details = {}
        
        if not raw_response:
            return predicted_details
        
        # Intento 1: JSON válido completo
        try:
            parsed_json = json.loads(raw_response)
            if "clasificaciones" in parsed_json:
                for item in parsed_json.get("clasificaciones", []):
                    if "codigo" in item and "justificacion" in item:
                        predicted_details[str(item["codigo"])] = item["justificacion"]
                return predicted_details
        except json.JSONDecodeError:
            pass
        
        # Intento 2: Regex para bloques completos de clasificaciones
        pattern_completo = re.compile(
            r'\{\s*"codigo":\s*"(?P<code>\d+)",\s*"justificacion":\s*"(?P<just>.*?)"\s*\}', 
            re.DOTALL
        )
        for match in pattern_completo.finditer(raw_response):
            predicted_details[match.group("code")] = match.group("just")
        
        # Intento 3: Último bloque truncado
        pattern_truncado = re.compile(
            r'\{\s*"codigo":\s*"(?P<code>\d+)",\s*"justificacion":\s*"(?P<just>.*)', 
            re.DOTALL
        )
        last_brace_pos = raw_response.rfind('{')
        if last_brace_pos != -1:
            match_truncado = pattern_truncado.search(raw_response[last_brace_pos:])
            if match_truncado:
                code = match_truncado.group("code")
                if code not in predicted_details:
                    justification = match_truncado.group("just") + " [TRUNCADO]"
                    predicted_details[code] = justification
        
        return predicted_details
    
    def create_nested_format(self, unified_data: Dict) -> int:
        # Asegurar que existe el directorio
        self.dataset_paths['anidado'].parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.dataset_paths['anidado'], 'w', encoding='utf-8') as f:
            for record in unified_data.values():
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        return len(unified_data)
    
    def create_unnested_format(self, unified_data: Dict, reference_data: Dict) -> Tuple[int, List[Dict]]:
        final_rows = []
        parsing_issues = []
        
        for obs_id, unified_record in unified_data.items():
            ref_record = reference_data.get(obs_id)
            if not ref_record:
                continue
            
            # Parsear predicciones detalladas desde la respuesta de la API
            predicted_details = self.parse_detailed_predictions(
                unified_record.get("raw_response", "")
            )
            
            # Verificar consistencia entre códigos en lista y códigos parseados
            predicted_from_details = set(predicted_details.keys())
            predicted_from_list = set(str(c) for c in unified_record.get("predicted_codes", []))
            
            if predicted_from_details != predicted_from_list:
                parsing_issues.append({
                    "id": obs_id,
                    "codes_list": sorted(list(predicted_from_list)),
                    "codes_parsed": sorted(list(predicted_from_details))
                })
            
            # --- MODO COMPLEX: Expandir por cada ID de delito original ---
            if PROCESSING_MODE == "complex":
                # Extraer IDs de delito originales desde el archivo de referencia
                try:
                    assistant_content = json.loads(ref_record["messages"][2]["content"])
                    crime_ids = assistant_content.get("ids_delito_originales", [])
                except (json.JSONDecodeError, KeyError, IndexError):
                    crime_ids = [None]
                
                if not crime_ids:
                    crime_ids = [None]
                
                # Expandir por cada ID de delito original
                for crime_id in crime_ids:
                    row = {
                        "id_delito_ia": crime_id,
                        "id_observacion": obs_id,
                        "observacion": unified_record.get("observacion"),
                        "expected_codes_obs": unified_record.get("expected_codes", []),
                        "predicted_codes_obs": unified_record.get("predicted_codes", []),
                        "razonamiento_general_modelo": unified_record.get("razonamiento_modelo"),
                        "predicciones_detalladas_modelo": predicted_details,
                        "timestamp": unified_record.get("timestamp"),
                        "processing_error": unified_record.get("error", False)
                    }
                    final_rows.append(row)
            
            # --- MODO SIMPLE: Sin expansión, 1:1 ---
            else:
                row = {
                    "id_delito_ia": obs_id,  # El ID es el que viene de la API
                    "id_observacion": obs_id,
                    "observacion": unified_record.get("observacion"),
                    "expected_codes_obs": unified_record.get("expected_codes", []),
                    "predicted_codes_obs": unified_record.get("predicted_codes", []),
                    "razonamiento_general_modelo": unified_record.get("razonamiento_modelo"),
                    "predicciones_detalladas_modelo": predicted_details,
                    "timestamp": unified_record.get("timestamp"),
                    "processing_error": unified_record.get("error", False)
                }
                final_rows.append(row)
        
        # Asegurar que existe el directorio
        self.dataset_paths['desanidado'].parent.mkdir(parents=True, exist_ok=True)
        
        # Guardar archivo desanidado
        with open(self.dataset_paths['desanidado'], 'w', encoding='utf-8') as f:
            for row in final_rows:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        
        return len(final_rows), parsing_issues
    
    def process(self) -> Dict:
        try:
            unified_data = self.load_batch_files()
            
            reference_data = self.load_reference_data()
            
            self.validate_consistency(unified_data, reference_data)
            
            nested_count = self.create_nested_format(unified_data)
            
            unnested_count, parsing_issues = self.create_unnested_format(unified_data, reference_data)
            
            results = {
                'dataset_name': self.dataset_name,
                'unified_records': len(unified_data),
                'reference_records': len(reference_data),
                'nested_file': self.dataset_paths['anidado'],
                'unnested_file': self.dataset_paths['desanidado'],
                'nested_count': nested_count,
                'unnested_count': unnested_count,
                'parsing_issues_count': len(parsing_issues),
                'parsing_issues': parsing_issues[:10]
            }
            
            print(f"Anidado: {nested_count} registros | Desanidado: {unnested_count} registros")
            if parsing_issues:
                print(f"⚠️  Problemas de parseo: {len(parsing_issues)} casos")
            
            return results
            
        except Exception as e:
            print(f"\n❌ ERROR DURANTE EL PROCESAMIENTO:")
            print(f"   {e}")
            import traceback
            traceback.print_exc()
            return None

def detect_dataset():
    results_dir = config.paths.results_dir
    
    if not results_dir.exists():
        raise FileNotFoundError(f"No existe directorio de resultados: {results_dir}")
    
    # Buscar directorios de datasets con estructura esperada
    dataset_dirs = []
    for item in results_dir.iterdir():
        if item.is_dir() and (item / "Lotes").exists():
            dataset_dirs.append(item)
    
    if not dataset_dirs:
        raise FileNotFoundError("No se encontraron datasets con estructura de lotes")
    
    if len(dataset_dirs) == 1:
        return dataset_dirs[0].name
    
    # Si hay múltiples, mostrar opciones
    print("📂 Datasets disponibles:")
    for i, dataset_dir in enumerate(dataset_dirs, 1):
        lotes_count = len(list((dataset_dir / "Lotes").glob("*.jsonl")))
        print(f"   {i}. {dataset_dir.name} ({lotes_count} lotes)")
    
    try:
        selection = int(input("\nSelecciona el dataset (número): ")) - 1
        if 0 <= selection < len(dataset_dirs):
            return dataset_dirs[selection].name
        else:
            raise ValueError("Selección fuera de rango")
    except (ValueError, KeyboardInterrupt):
        raise ValueError("Selección inválida o cancelada")

def main():
    print("=" * 80)
    print("UNIFICACIÓN DE LOTES")
    print("=" * 80)
    
    try:
        # Detectar dataset automáticamente
        dataset_name = detect_dataset()
        print(f"Dataset seleccionado: {dataset_name}")
        
        # Verificar estructura del dataset
        dataset_paths = config.get_dataset_paths(dataset_name)
        
        if not dataset_paths['lotes_dir'].exists():
            raise FileNotFoundError(f"No existe directorio de lotes: {dataset_paths['lotes_dir']}")
        
        if not dataset_paths['clean'].exists():
            raise FileNotFoundError(f"No existe archivo de referencia: {dataset_paths['clean']}")
        
        lote_files = list(dataset_paths['lotes_dir'].glob("*.jsonl"))
        if not lote_files:
            raise FileNotFoundError("No se encontraron archivos de lotes")
        
        # Inicializar procesador
        processor = ResultProcessor(dataset_name)
        
        # Ejecutar procesamiento
        results = processor.process()
        
        return 0 if results else 1
        
    except KeyboardInterrupt:
        print("\n\nProcesamiento interrumpido por el usuario")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)