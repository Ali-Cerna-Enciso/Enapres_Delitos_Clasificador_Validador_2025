#!/usr/bin/env python3
"""
Script 6: Analizador de Errores de API
Analiza respuestas de la API, identifica problemas de formato y guarda casos para revisión.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

# Agregar el directorio raíz del proyecto al path de Python
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

try:
    from src.config.config_manager import config
except Exception as e:
    print(f"⚠️  Advertencia: No se pudo cargar config: {e}")
    config = None

# Obtener modo de procesamiento desde config
PROCESSING_MODE = config.get_processing_mode() if config else "complex"

class ErrorAnalyzer:

    def __init__(self, dataset_name):
        self.dataset_name = dataset_name
        self.results_dir = Path("data/results") / dataset_name
        self.nested_file = self.results_dir / f"anidado_{dataset_name}.jsonl"
        self.errors_dir = self.results_dir / "Errores"
        self.errors_dir.mkdir(exist_ok=True)

        # Contadores de errores
        self.json_decode_errors = 0
        self.parse_errors = 0
    
    def classify_record(self, record):
        razonamiento = record.get("razonamiento_modelo", "")
        raw_response = record.get("raw_response", "")

        is_fallback = "fallback" in razonamiento.lower()
        is_raw_valid_json = False
        has_clasificaciones = False

        if raw_response:
            try:
                parsed_raw = json.loads(raw_response)
                is_raw_valid_json = True
                if "clasificaciones" in parsed_raw and parsed_raw["clasificaciones"]:
                    has_clasificaciones = True
            except json.JSONDecodeError:
                is_raw_valid_json = False

        if not is_fallback and is_raw_valid_json and has_clasificaciones:
            return "Formato A: Perfecto"
        elif is_fallback and is_raw_valid_json and has_clasificaciones:
            return "Formato B: Fallback Recuperable"
        elif is_fallback and not is_raw_valid_json:
            return "Formato C: Fallback Truncado"
        elif not is_fallback and (not is_raw_valid_json or not has_clasificaciones):
            return "Formato D: Inconsistente"
        else:
            return "Formato E: Otro"
    
    def analyze_errors(self):
        if not self.nested_file.exists():
            raise FileNotFoundError(f"No se encuentra archivo anidado: {self.nested_file}")
        
        classified_records = defaultdict(list)
        total_records = 0
        
        # Clasificar todos los registros
        with open(self.nested_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line)
                    format_name = self.classify_record(record)
                    classified_records[format_name].append(record)
                    total_records += 1
                except json.JSONDecodeError as e:
                    self.json_decode_errors += 1
                    error_record = {
                        "linea": line_num,
                        "error": str(e)[:100],
                        "contenido_parcial": line[:100]
                    }
                    classified_records["Error de Lectura"].append(error_record)
                    print(f"⚠️  Error JSON en línea {line_num}: {str(e)[:50]}")
                except Exception as e:
                    self.parse_errors += 1
                    print(f"⚠️  Error inesperado en línea {line_num}: {str(e)[:50]}")
        
        if total_records == 0:
            raise ValueError("No se encontraron registros válidos")

        # Reportar errores de parseo
        if self.json_decode_errors > 0 or self.parse_errors > 0:
            print(f"\n⚠️  Errores durante análisis:")
            print(f"   - Errores JSON: {self.json_decode_errors}")
            print(f"   - Errores de parseo: {self.parse_errors}")

        return classified_records, total_records
    
    def generate_report(self, classified_records, total_records):
        print(f"Total de registros: {total_records}")
        print()
        
        for format_name, records in sorted(classified_records.items()):
            count = len(records)
            percentage = (count / total_records) * 100
            print(f"  - {format_name}: {count} ({percentage:.1f}%)")
            
            if "Truncado" in format_name or "Inconsistente" in format_name:
                examples = [rec.get('id', 'ID_no_encontrado') for rec in records[:2]]
                if examples:
                    print(f"    Ejemplos: {', '.join(examples)}")
    
    def save_problematic_cases(self, classified_records):
        
        casos_truncados = classified_records.get("Formato C: Fallback Truncado", [])
        casos_inconsistentes = classified_records.get("Formato D: Inconsistente", [])
        
        files_created = []
        
        if casos_truncados:
            truncados_path = self.errors_dir / "formato_c_truncados.jsonl"
            with open(truncados_path, 'w', encoding='utf-8') as f:
                for record in casos_truncados:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            files_created.append(truncados_path)
        
        if casos_inconsistentes:
            inconsistentes_path = self.errors_dir / "formato_d_inconsistentes.jsonl"
            with open(inconsistentes_path, 'w', encoding='utf-8') as f:
                for record in casos_inconsistentes:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            files_created.append(inconsistentes_path)
        
        return files_created
    
    def run_analysis(self):
        try:
            # Analizar errores
            classified_records, total_records = self.analyze_errors()
            
            # Generar reporte
            self.generate_report(classified_records, total_records)
            
            # Guardar casos problemáticos
            files_created = self.save_problematic_cases(classified_records)
            
            # Resumen
            problematic_count = (
                len(classified_records.get("Formato C: Fallback Truncado", [])) +
                len(classified_records.get("Formato D: Inconsistente", []))
            )
            
            return {
                'total_records': total_records,
                'problematic_cases': problematic_count,
                'files_created': files_created,
                'classification_summary': {k: len(v) for k, v in classified_records.items()}
            }
            
        except Exception as e:
            print(f"Error durante el análisis: {e}")
            raise

def main():
    dataset_name = config.default_dataset_name if config else None
    
    if not dataset_name:
        print("❌ ERROR: No se pudo obtener dataset desde config")
        sys.exit(1)
    
    anidado_file = Path("data/results") / dataset_name / f"anidado_{dataset_name}.jsonl"
    
    if not anidado_file.exists():
        print(f"❌ ERROR: Archivo anidado no encontrado")
        print(f"   Buscando: {anidado_file}")
        sys.exit(1)
    
    print("="*80)
    print("ANÁLISIS DE ERRORES DE API")
    print("="*80)
    
    analyzer = ErrorAnalyzer(dataset_name)
    results = analyzer.run_analysis()
    
    print(f"\n✅ Análisis completado - Casos problemáticos: {results['problematic_cases']}")

if __name__ == "__main__":
    main()