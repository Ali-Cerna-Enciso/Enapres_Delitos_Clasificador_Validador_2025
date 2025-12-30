#!/usr/bin/env python3
"""
Script 7: Generador de Reportes Excel
Procesa resultados de la API y genera reportes de análisis en Excel.
"""

import pandas as pd
import sys
import json
import re
from pathlib import Path
import os

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

class ExcelAnalysisGenerator:
    
    def __init__(self, dataset_name):
        self.dataset_name = dataset_name
        self.results_dir = Path("data/results") / dataset_name
        
        # Rutas de archivos
        self.input_file = self.results_dir / f"desanidado_{dataset_name}.jsonl"
        self.output_file = self.results_dir / f"analisis_{dataset_name}.xlsx"
    
    def _get_available_filename(self, base_path: Path) -> Path:
        """
        Encuentra un nombre de archivo disponible.
        Si el archivo base está abierto/bloqueado, retorna versión numerada (_1, _2, etc.)
        
        Args:
            base_path: Ruta del archivo deseado (ej: analisis_Test_Nuevo.xlsx)
        
        Returns:
            Path del archivo disponible para escritura
        """
        # Intentar con el nombre original primero
        if self._can_write_file(base_path):
            return base_path
        
        # Si está bloqueado, buscar versión numerada disponible
        stem = base_path.stem  # nombre sin extensión
        suffix = base_path.suffix  # extensión
        parent = base_path.parent
        
        version = 1
        while True:
            versioned_path = parent / f"{stem}_{version}{suffix}"
            if self._can_write_file(versioned_path):
                print(f"⚠️  Archivo '{base_path.name}' está abierto o bloqueado")
                print(f"   Guardando como: '{versioned_path.name}'")
                return versioned_path
            version += 1
            
            # Límite de seguridad para evitar bucle infinito
            if version > 100:
                raise RuntimeError(f"No se pudo encontrar nombre disponible después de 100 intentos")
    
    def _can_write_file(self, file_path: Path) -> bool:
        """
        Verifica si un archivo puede ser escrito (no está abierto/bloqueado).
        
        Args:
            file_path: Ruta del archivo a verificar
        
        Returns:
            True si el archivo puede ser escrito, False si está bloqueado
        """
        # Si el archivo no existe, está disponible
        if not file_path.exists():
            return True
        
        # Intentar abrir el archivo en modo escritura exclusivo
        try:
            # En Windows, intentar renombrar el archivo a sí mismo
            # Falla si está abierto en otra aplicación
            if os.name == 'nt':  # Windows
                os.rename(file_path, file_path)
            else:  # Linux/Mac
                # Intentar abrir en modo append
                with open(file_path, 'a'):
                    pass
            return True
        except (OSError, PermissionError):
            return False
    
    def clean_reasoning(self, text):
        if not isinstance(text, str):
            return text
        
        # Eliminar punto 5 (plantilla)
        cleaned_text = re.sub(r"\s*5\.\s*Construyo el JSON final.*", "", text, flags=re.DOTALL)
        
        # Patrones genéricos del punto 4 a eliminar
        generic_patterns = [
            r"No hay más eventos delictivos mencionados en la observación\.",
            r"No hay otros eventos delictivos mencionados en la observación.*",
            r"No hay más eventos delictivos en la observación\."
        ]
        
        # Buscar punto 4
        match_point_4 = re.search(r"(\s*4\.\s*)(.*)", cleaned_text, flags=re.DOTALL)
        
        if match_point_4:
            content_point_4 = match_point_4.group(2).strip()
            is_generic = any(re.fullmatch(pattern, content_point_4, re.IGNORECASE) 
                           for pattern in generic_patterns)
            
            if is_generic:
                cleaned_text = re.sub(r"\s*4\.\s*.*", "", cleaned_text, flags=re.DOTALL)
        
        return cleaned_text.strip()
    
    def process_data(self):
        if not self.input_file.exists():
            raise FileNotFoundError(f"No se encuentra archivo desanidado: {self.input_file}")
        
        # Leer archivo JSONL con manejo robusto de errores
        try:
            df = pd.read_json(self.input_file, lines=True, encoding='utf-8')
        except (UnicodeDecodeError, pd.errors.ParserError):
            # Intenta con encoding diferente si falla
            try:
                df = pd.read_json(self.input_file, lines=True, encoding='latin-1')
            except Exception as e:
                raise ValueError(f"No se pudo leer el archivo desanidado: {e}")
        
        # Validar que exista la columna requerida
        if 'id_observacion' not in df.columns:
            raise ValueError(f"Columna 'id_observacion' no encontrada en archivo desanidado")
        
        # Eliminar filas con id_observacion nulo
        df = df.dropna(subset=['id_observacion'])
        
        if len(df) == 0:
            raise ValueError("No hay registros válidos en archivo desanidado")
        
        # Resetear índice para evitar problemas con iterrows
        df = df.reset_index(drop=True)
        
        # --- MODO SIMPLE: Solo razonamiento ---
        if PROCESSING_MODE == "simple":
            output_rows = []
            for _, row in df.iterrows():
                general_reasoning = self.clean_reasoning(
                    row.get('razonamiento_general_modelo', 'Sin razonamiento general.')
                )
                
                final_row = {
                    "ID_DELITO_IA": row['id_delito_ia'],
                    "OBSERVACION": row['observacion'],
                    "CODIGOS_PREDICHOS": ', '.join(str(c) for c in row.get('predicted_codes_obs', [])) or "Ninguno",
                    "RAZONAMIENTO_GENERAL": general_reasoning
                }
                output_rows.append(final_row)
            
            return pd.DataFrame(output_rows)
        
        # --- MODO COMPLEX: Con análisis de errores ---
        output_rows = []
        
        for obs_id, group in df.groupby('id_observacion', as_index=False):
            common_info = group.iloc[0]
            predicted_details = common_info.get('predicciones_detalladas_modelo', {})
            all_predicted_codes = set(common_info.get('predicted_codes_obs', []))
            expected_codes = set(common_info.get('expected_codes_obs', []))
            general_reasoning = self.clean_reasoning(
                common_info.get('razonamiento_general_modelo', 'Sin razonamiento general.')
            )
            
            # Calcular si hubo algún error (Falso Positivo o Falso Negativo)
            hubo_errores = expected_codes != all_predicted_codes
            
            # Preparar la información de Falsos Positivos
            falsos_positivos = all_predicted_codes - expected_codes
            fp_info_list = [
                f"Código FP: {code} | Justificación: {predicted_details.get(code, 'TRUNCADA/NO DISPONIBLE')}"
                for code in sorted(list(falsos_positivos))
            ]
            fp_info_str = "\n".join(fp_info_list) if fp_info_list else None
            falsos_negativos = expected_codes - all_predicted_codes
            
            for index, row in group.iterrows():
                delito_esperado_code = str(row['id_delito_ia'].split('-')[-1]) if pd.notna(row['id_delito_ia']) else None
                match_delito = delito_esperado_code in all_predicted_codes if delito_esperado_code else False
                
                final_row = {
                    "ID_DELITO_IA": row['id_delito_ia'],
                    "MATCH_DELITO": match_delito,
                    "OBSERVACION": row['observacion'],
                    "DELITO_ESPERADO": delito_esperado_code,
                    "JUSTIFICACION_ACIERTO": None,
                    "DETALLE_ERRORES_MODELO": None,
                    "RAZONAMIENTO_GENERAL": general_reasoning,
                    "ESTADO_REVISION": None  
                }
                
                # 3. Aplicar la lógica condicional para llenar las columnas

                if match_delito:  # El delito de ESTA fila fue un acierto
                    final_row["ESTADO_REVISION"] = 1  # 1. Registro correcto
                    final_row["JUSTIFICACION_ACIERTO"] = predicted_details.get(
                        delito_esperado_code, "Justificación TRUNCADA/NO DISPONIBLE"
                    )
                    # Lógica para DETALLE_ERRORES_MODELO
                    if falsos_positivos and not falsos_negativos:
                        final_row["DETALLE_ERRORES_MODELO"] = fp_info_str
                
                else:  # El delito de ESTA fila fue un Falso Negativo
                    # Verificar si el modelo asignó código 30 (observación ambigua)
                    if "30" in all_predicted_codes:
                        final_row["ESTADO_REVISION"] = 3  # 3. Mejorar observación
                    elif all_predicted_codes:
                        final_row["ESTADO_REVISION"] = 2  # 2. Corrección de variable
                    else:
                        final_row["ESTADO_REVISION"] = 5  # 5. Eliminar
                    
                    # Lógica para DETALLE_ERRORES_MODELO
                    error_parts = []
                    if fp_info_str:
                        error_parts.append(fp_info_str)
                    
                    fn_info = f"FN: El código esperado '{delito_esperado_code}' no fue detectado."
                    error_parts.append(fn_info)
                    
                    final_row["DETALLE_ERRORES_MODELO"] = "\n---\n".join(error_parts)
                # Caso especial: Modelo no predijo nada en absoluto
                if not all_predicted_codes and delito_esperado_code:
                    final_row["DETALLE_ERRORES_MODELO"] = f"ERROR: El modelo no detectó ningún delito. Se esperaba el código '{delito_esperado_code}' Revisar justificación."
                output_rows.append(final_row)
        
        return pd.DataFrame(output_rows)
    
    def generate_excel(self):
        df = self.process_data()
        
        # Definir orden de columnas según el modo
        if PROCESSING_MODE == "simple":
            column_order = [
                "ID_DELITO_IA",
                "OBSERVACION",
                "CODIGOS_PREDICHOS",
                "RAZONAMIENTO_GENERAL"
            ]
        else:  # complex
            column_order = [
                "ID_DELITO_IA",
                "MATCH_DELITO",
                "ESTADO_REVISION",  
                "OBSERVACION",
                "DELITO_ESPERADO",
                "JUSTIFICACION_ACIERTO",
                "DETALLE_ERRORES_MODELO", 
                "RAZONAMIENTO_GENERAL"
            ]
        
        df = df[column_order]
        
        # Obtener nombre de archivo disponible (con versionado si está bloqueado)
        output_file = self._get_available_filename(self.output_file)
        
        # Guardar Excel
        df.to_excel(output_file, index=False, engine='openpyxl')
        return output_file
    
    def get_summary_stats(self):
        df = self.process_data()
        
        total_records = len(df)
        
        if PROCESSING_MODE == "simple":
            return {
                'total_records': total_records,
                'matches': None,
                'match_rate': None,
                'mode': 'simple'
            }
        else:  # complex
            matches = df['MATCH_DELITO'].sum()
            match_rate = (matches / total_records) * 100 if total_records > 0 else 0
            
            return {
                'total_records': total_records,
                'matches': matches,
                'match_rate': match_rate,
                'false_negatives': total_records - matches
            }

def main():
    dataset_name = config.default_dataset_name if config else None
    
    if not dataset_name:
        print("❌ ERROR: No se pudo obtener dataset desde config")
        sys.exit(1)
    
    desanidado_file = Path("data/results") / dataset_name / f"desanidado_{dataset_name}.jsonl"
    
    if not desanidado_file.exists():
        print(f"❌ ERROR: Archivo desanidado no encontrado")
        print(f"   Buscando: {desanidado_file}")
        sys.exit(1)
    
    print("="*80)
    print("GENERACIÓN DE REPORTE EXCEL")
    print("="*80)
    
    generator = ExcelAnalysisGenerator(dataset_name)
    output_file = generator.generate_excel()
    stats = generator.get_summary_stats()
    
    print(f"Registros: {stats['total_records']} | Aciertos: {stats['matches']} ({stats['match_rate']:.1f}%)")
    print(f"✅ Excel creado: {output_file.name}")

if __name__ == "__main__":
    main()