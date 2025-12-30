#!/usr/bin/env python3
"""Validador de delitos vía API con procesamiento asíncrono en lotes"""

import os
import gc
import json
import asyncio
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
from tqdm.asyncio import tqdm_asyncio
from openai import AsyncOpenAI

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.config.config_manager import config
from src.prompts.crime_validation_prompts import get_knowledge_base
from src.utils import get_project_logger

logger = get_project_logger(__name__)

class AsyncAPIDelitoValidator:
    
    def __init__(self, knowledge_base=None, dataset_name: str = None, max_concurrent: int = 10):
        """Inicializa validador con knowledge base y configuración"""
        if knowledge_base is None:
            prompt_version = config.get_prompts_version()
            knowledge_base = get_knowledge_base(version=prompt_version)
        
        if dataset_name is None:
            dataset_name = config.default_dataset_name
        
        logger.info(f"Inicializando validador para dataset: {dataset_name}")
        
        self.api_client = AsyncOpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url=config.api.base_url
        )
        
        self.knowledge_base = knowledge_base
        self.dataset_name = dataset_name
        self.max_concurrent = max_concurrent
        self.results_saved = 0
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.dataset_paths = config.get_dataset_paths(dataset_name)
        config.create_dataset_structure(dataset_name)
    
    async def generate_prediction_api(self, system_prompt: str, user_prompt: str, case_id: str) -> str:
        max_retries = config.api.max_retries
        base_timeout = config.api.timeout
        base_delay = 2

        for attempt in range(max_retries):
            try:
                # Timeout incremental: aumenta con cada reintento
                current_timeout = base_timeout + (attempt * 30)  # +30s por cada reintento

                async with self.semaphore:
                    response = await self.api_client.chat.completions.create(
                        model=config.api.model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens=config.api.max_tokens,
                        temperature=config.api.temperature,
                        top_p=config.api.top_p,
                        timeout=current_timeout,  # Timeout incremental
                        response_format={"type": "json_object"}
                    )
                    return response.choices[0].message.content.strip()

            except Exception as e:
                error_type = type(e).__name__
                error_str = str(e).lower()

                # Backoff exponencial con jitter
                if attempt < max_retries - 1:
                    # Backoff exponencial: 2^(attempt+1) + jitter
                    import random
                    backoff = (base_delay ** (attempt + 1))
                    jitter = random.uniform(0, attempt * 0.5)
                    wait_time = backoff + jitter

                    # Casos especiales
                    if "RateLimitError" in error_type or "rate_limit" in error_str:
                        # Rate limit: usar delay configurado + backoff
                        wait_time = config.api.retry_delay + (attempt * 15)
                        print(f"[{case_id}] Rate limit (intento {attempt + 1}/{max_retries}) - esperando {wait_time:.1f}s")

                    elif "timeout" in error_str or "timed out" in error_str:
                        # Timeout: próximo intento con timeout más largo
                        next_timeout = base_timeout + ((attempt + 1) * 30)
                        print(f"[{case_id}] Timeout (intento {attempt + 1}/{max_retries}) - próximo timeout: {next_timeout}s, esperando {wait_time:.1f}s")

                    elif "connection" in error_str or "network" in error_str:
                        # Error de red: esperar más tiempo
                        wait_time = backoff * 2 + jitter
                        print(f"[{case_id}] Error de red (intento {attempt + 1}/{max_retries}) - esperando {wait_time:.1f}s")

                    else:
                        print(f"[{case_id}] Error {error_type} (intento {attempt + 1}/{max_retries}) - esperando {wait_time:.1f}s")

                    await asyncio.sleep(wait_time)
                else:
                    # Último intento fallido
                    logger.error(f"[{case_id}] Error final después de {max_retries} intentos: {error_type} - {str(e)[:100]}")
                    print(f"[{case_id}] ❌ Error final después de {max_retries} intentos: {error_type} - {str(e)[:100]}")
                    return '{"razonamiento": "ERROR: Máximo de reintentos alcanzado después de múltiples intentos con timeout incremental", "clasificaciones": []}'

        return '{"razonamiento": "ERROR en llamada API", "clasificaciones": []}'
    
    def parse_response(self, response: str) -> Tuple[List[str], str]:
        try:
            data = json.loads(response.strip())
            razonamiento = data.get("razonamiento", "No se encontró razonamiento.")
            clasificaciones = data.get("clasificaciones", [])
            codigos = sorted([str(item.get("codigo", "")) for item in clasificaciones if isinstance(item, dict) and item.get("codigo")])
            return codigos, razonamiento
        except json.JSONDecodeError:
            try:
                json_match = re.search(r'\{.*?"clasificaciones":\s*\[.*?\]\s*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    razonamiento = data.get("razonamiento", "Razonamiento extraído parcialmente.")
                    clasificaciones = data.get("clasificaciones", [])
                    codigos = sorted([str(item.get("codigo", "")) for item in clasificaciones if isinstance(item, dict) and item.get("codigo")])
                    return codigos, razonamiento
            except:
                pass
        
        try:
            codes_matches = re.findall(r'"codigo":\s*"(\d+)"', response)
            if codes_matches:
                return sorted(list(set(codes_matches))), "Códigos extraídos con regex."
        except:
            pass
        
        return [], f"Error de parseo - respuesta no válida: {response[:100]}..."
    
    async def process_single_case(self, case_data: Dict) -> Dict:
        try:
            case_id = case_data.get("id", "unknown")
            observacion = case_data.get("observacion", "")

            # Manejar codigos_esperados de forma defensiva y robusta
            codigos_raw = case_data.get("codigos_esperados", [])

            # Normalizar a lista si es string único
            if isinstance(codigos_raw, str):
                codigos_raw = [codigos_raw] if codigos_raw.strip() else []
            elif not isinstance(codigos_raw, list):
                codigos_raw = []

            # Procesar y filtrar códigos válidos
            expected_codes = []
            for c in codigos_raw:
                if isinstance(c, (int, float)) and not (isinstance(c, float) and c != c):  # Excluir NaN
                    expected_codes.append(str(int(c)))
                elif isinstance(c, str) and c.strip():
                    expected_codes.append(c.strip())
                elif isinstance(c, dict) and "codigo" in c:
                    codigo_val = c.get("codigo")
                    if codigo_val is not None and str(codigo_val).strip():
                        expected_codes.append(str(codigo_val).strip())

            # Eliminar duplicados y ordenar
            expected_codes = sorted(list(set(expected_codes)))

            ids_delito_originales = case_data.get("ids_delito_originales", [])
            
            system_prompt, user_prompt = self.knowledge_base.get_validation_prompt(observacion)
            raw_response = await self.generate_prediction_api(system_prompt, user_prompt, case_id)
            predicted_codes, razonamiento = self.parse_response(raw_response)
            
            return {
                "id": case_id,
                "observacion": observacion,
                "expected_codes": expected_codes,
                "ids_delito_originales": ids_delito_originales,
                "predicted_codes": predicted_codes,
                "razonamiento_modelo": razonamiento,
                "raw_response": raw_response,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            import traceback
            logger.error(f"Error procesando caso {case_data.get('id', 'unknown')}: {e}", exc_info=True)
            print(f"Error procesando caso {case_data.get('id', 'unknown')}: {e}")
            traceback.print_exc()
            return {
                "id": case_data.get("id", "unknown"),
                "observacion": case_data.get("observacion", ""),
                "expected_codes": case_data.get("codigos_esperados", []),
                "ids_delito_originales": case_data.get("ids_delito_originales", []),
                "predicted_codes": [],
                "razonamiento_modelo": f"Error en procesamiento: {e}",
                "raw_response": "",
                "timestamp": datetime.now().isoformat(),
                "error": True
            }
    
    async def process_batch_async(self, batch_data: List[Dict], batch_id: int) -> List[Dict]:
        tasks = [self.process_single_case(case_data) for case_data in batch_data]
        results = await tqdm_asyncio.gather(*tasks, desc=f"Lote {batch_id}")
        return results
    
    def save_batch_results(self, results: List[Dict], batch_id: int) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"resultados_lote_{batch_id}_{timestamp}.jsonl"
        filepath = self.dataset_paths['lotes_dir'] / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for result in results:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
        
        self.results_saved += len(results)
        logger.info(f"Lote {batch_id} guardado: {len(results)} resultados en {filename}")
        return filename
    

def load_clean_data(dataset_name: str) -> tuple[List[Dict], int]:
    dataset_paths = config.get_dataset_paths(dataset_name)
    clean_file_path = dataset_paths['clean']
    
    if not clean_file_path.exists():
        raise FileNotFoundError(f"No se encuentra archivo limpio: {clean_file_path}")
    
    data = []
    total_records_original = 0
    with open(clean_file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line.strip())
                if "messages" in record and len(record["messages"]) >= 3:
                    observacion = record["messages"][1]["content"]
                    assistant_content = json.loads(record["messages"][2]["content"])
                    ids_originales = assistant_content.get("ids_delito_originales", [])
                    total_records_original += len(ids_originales)
                    data.append({
                        "id": record.get("id"),
                        "observacion": observacion,
                        "codigos_esperados": assistant_content.get("codigos_delito", []),
                        "ids_delito_originales": ids_originales
                    })
            except Exception:
                pass
    
    return data, total_records_original

async def run_validation_async(dataset_name: str, max_concurrent: int = 1, 
                               batch_size: int = None, auto_confirm: bool = True, 
                               show_header: bool = True, api_key: str = None):
    if show_header:
        print("="*80)
        print("VALIDACIÓN VÍA API")
        print("="*80)
    
    if not api_key:
        api_key = config.get_api_key("deepseek")
    
    if show_header:
        print("\n" + "="*80)
        print("RESUMEN DE DATOS A VALIDAR")
        print("="*80)
    
    try:
        prompt_version = config.get_prompts_version()
        
        knowledge_base = get_knowledge_base(version=prompt_version)
        
        if show_header:
            print(f"📋 Versión de prompts cargada: V{prompt_version}")
        
        if hasattr(knowledge_base, 'version'):
            kb_version = knowledge_base.version
            if show_header:
                print(f"✓ Knowledge Base inicializada: Versión {kb_version}")
            if str(kb_version) != str(prompt_version):
                print(f"❌ ERROR: Se esperaba V{prompt_version} pero se cargó V{kb_version}")
                return False
        elif hasattr(knowledge_base, 'description'):
            if show_header:
                print(f"✓ Knowledge Base inicializada: {knowledge_base.description}")
        
        if show_header:
            print()
        
        data_to_process, total_original = load_clean_data(dataset_name)
        logger.info(f"Cargados {len(data_to_process)} casos para procesar (de {total_original} registros originales)")
        
        if not data_to_process:
            logger.warning("No hay datos para procesar")
            print("No hay datos para procesar")
            return True  # Retorna True (completó, aunque sin datos)
        
        total_cases = len(data_to_process)
        batch_size = batch_size or config.processing.batch_size
        num_batches = (total_cases + batch_size - 1) // batch_size
        
        if show_header:
            # Obtener modo de procesamiento
            processing_mode = config.get_processing_mode() if config else "complex"
            
            print(f"\n📊 CONFIGURACIÓN DEL SISTEMA")
            print(f"  ├─ Modo de procesamiento: {processing_mode.upper()}")
            print(f"  └─ Versión de prompts: V{prompt_version}")
            
            print(f"\n📁 Base de datos elegida para procesar:")
            print(f"  └─ {dataset_name}.xlsx")
            
            print(f"\n📈 Cantidad de datos:")
            print(f"  ├─ Registros originales en Excel: {total_original}")
            print(f"  └─ Observaciones únicas a procesar: {total_cases}")
            
            print(f"\n🔑 Verificación de Clave API:")
            print(f"  └─ ...{api_key[-5:]} ✓")
            
            print(f"\n⚙️  Configuración de procesamiento:")
            print(f"  ├─ Tamaño de lote: {batch_size}")
            print(f"  ├─ Total de lotes: {num_batches}")
            print(f"  ├─ Workers paralelos: {max_concurrent}")
            print(f"  └─ Estimación: {total_cases / (max_concurrent * 6):.1f} minutos")
        
        if not auto_confirm:
            print("\n" + "=" * 80)
            confirm = input("¿Deseas proceder con la validación? (Y/n): ").lower()
            if confirm in ['n', 'no']:
                print("\n⏸️  Proceso cancelado por el usuario.")
                return False  # Retorna False indicando que se canceló
            print("=" * 80)
        
        # Crear backup de lotes antiguos antes de eliminar
        lotes_dir = config.get_dataset_paths(dataset_name)['lotes_dir']
        if lotes_dir.exists():
            old_files = list(lotes_dir.glob("resultados_*.jsonl"))
            if old_files:
                import shutil
                backup_dir = lotes_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                backup_dir.mkdir(parents=True, exist_ok=True)

                print(f"\n📦 Creando backup de {len(old_files)} archivos antiguos...")
                for old_file in old_files:
                    shutil.move(str(old_file), str(backup_dir / old_file.name))
                print(f"   ✓ Backup guardado en: {backup_dir.name}")
        
        validator = AsyncAPIDelitoValidator(knowledge_base, dataset_name, max_concurrent)
        
        start_time = datetime.now()
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_cases)
            batch_data = data_to_process[start_idx:end_idx]
            batch_id = batch_idx + 1
            
            print(f"\n{'-'*60}")
            print(f"LOTE {batch_id}/{num_batches} - Casos {start_idx + 1}-{end_idx}")
            print(f"{'-'*60}")
            
            batch_results = await validator.process_batch_async(batch_data, batch_id)
            filename = validator.save_batch_results(batch_results, batch_id)
            errors_count = sum(1 for r in batch_results if r.get('error', False))
            print(f"✅ Lote completado - Procesados: {len(batch_results)} | Errores: {errors_count}")
            print(f"   Guardado en: {filename}")
            
            if batch_idx % 3 == 0:
                gc.collect()
        
        processing_time = datetime.now() - start_time
        cases_per_minute = total_cases / (processing_time.total_seconds() / 60)
        
        logger.info(f"Procesamiento completado: {total_cases} casos en {processing_time} ({cases_per_minute:.1f} casos/min)")
        print(f"\n{'='*80}")
        print("✅ PROCESAMIENTO COMPLETADO")
        print(f"Tiempo: {processing_time} | Velocidad: {cases_per_minute:.1f} casos/min")
        print(f"{'='*80}")
        return True  # Retorna True indicando que completó exitosamente
        
    except KeyboardInterrupt:
        logger.warning("Procesamiento interrumpido por usuario")
        print("\nInterrumpido por usuario")
        return False  # Retorna False si se interrumpe
    except Exception as e:
        logger.error(f"Error en validación: {e}", exc_info=True)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False  # Retorna False si hay error

def run_validation(dataset_name: str, provider: str = "deepseek", auto_confirm: bool = True, show_header: bool = True, api_key: str = None):
    max_concurrent = 10
    return asyncio.run(run_validation_async(dataset_name, max_concurrent, auto_confirm=auto_confirm, show_header=show_header))

def main():
    dataset_name = config.default_dataset_name
    asyncio.run(run_validation_async(dataset_name, max_concurrent=10, auto_confirm=True))

if __name__ == "__main__":
    main()