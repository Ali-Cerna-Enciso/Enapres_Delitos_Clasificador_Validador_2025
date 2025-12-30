#!/usr/bin/env python3
"""
Script 2: Analizador y Limpiador de Patrones
Análisis de patrones redundantes y generación de observaciones limpias.
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter
from typing import List, Dict, Tuple

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

try:
    from src.config.config_manager import config
except Exception as e:
    print(f"Advertencia: No se pudo cargar config: {e}")
    config = None


class PatternAnalyzerCleaner:
    """Analiza y limpia patrones de observaciones"""
    
    def __init__(self, dataset_name: str):
        self.dataset_name = dataset_name
        self.paths = config.get_dataset_paths(dataset_name)
        self.patterns_by_length = {1: Counter(), 2: Counter(), 3: Counter()}
        self.total_observations = 0
        self.words_to_skip = {
            'ROBO', 'ROBO,','ROBARON', 'ROBAN', 'ROBAR', 'ROBADO', 'ROBADA', 'ROBOS',
            'HURTO', 'HURTARON', 'HURTAN', 'HURTAR', 'HURTADO', 'HURTADA', 'HURTOS',
            'SALTO', 'SALTARON', 'SALTAN', 'SALTAR', 'SALTADO', 'SALTADA', 'SALTOS', 
            'OFENSA', 'OFENSAS','INTENTO','INTENTARON','ESTAFA'
        }
    
    def extract_observation_starts(self, text: str, max_words: int = 3) -> List[str]:
        """Extrae las primeras 1, 2 y 3 palabras de una observación"""
        text = text.strip().upper()
        text = re.sub(r'\s+', ' ', text)
        
        words = text.split()
        phrases = []
        
        for length in range(1, min(max_words + 1, len(words) + 1)):
            phrase = ' '.join(words[:length])
            phrases.append(phrase)
        
        return phrases
    
    def count_syllables(self, word: str) -> int:
        """Cuenta sílabas en una palabra"""
        word = word.lower()
        word = re.sub(r'[^a-záéíóúüñ]', '', word)
        
        if not word:
            return 0
        
        vowels = 'aeiouáéíóúü'
        syllable_count = 0
        prev_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllable_count += 1
            prev_was_vowel = is_vowel
        
        return max(1, syllable_count)
    
    def analyze_patterns(self) -> Dict:
        """Analiza patrones de observaciones"""
        processed_file = self.paths['processed']
        
        if not processed_file.exists():
            print(f"Error: No se encuentra {processed_file}")
            return {}
        
        try:
            open_file = open(processed_file, 'r', encoding='utf-8')
        except (UnicodeDecodeError, UnicodeError):
            try:
                open_file = open(processed_file, 'r', encoding='latin-1')
            except Exception as e:
                print(f"Error: No se pudo leer archivo con ningún encoding: {e}")
                return {}
        
        try:
            with open_file as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if "messages" in data and len(data["messages"]) >= 2:
                            obs_content = data["messages"][1]["content"]
                            self.total_observations += 1
                            
                            phrases = self.extract_observation_starts(obs_content, max_words=3)
                            
                            for phrase in phrases:
                                phrase_length = len(phrase.split())
                                phrase_words = phrase.split()
                                should_skip = any(word in self.words_to_skip for word in phrase_words)
                                
                                if phrase_length == 1 and not should_skip:
                                    word = phrase_words[0]
                                    syllable_count = self.count_syllables(word)
                                    if syllable_count <= 2:
                                        should_skip = True
                                
                                if not should_skip:
                                    self.patterns_by_length[phrase_length][phrase] += 1
                    
                    except json.JSONDecodeError:
                        pass
                    except Exception:
                        pass
        finally:
            open_file.close()
        
        return self.patterns_by_length
    
    def display_patterns(self) -> Dict[int, List[Tuple[str, int, float]]]:
        """Analiza patrones y filtra según criterios de config"""
        pattern_min_count = config.processing.pattern_min_count if config else 10
        pattern_min_percent = config.processing.pattern_min_percent if config else 5.0
        
        patterns_to_remove = {1: [], 2: [], 3: []}
        
        for length in [3, 2, 1]:
            for phrase, count in self.patterns_by_length[length].most_common(None):
                percentage = (count / self.total_observations) * 100
                if count >= pattern_min_count and percentage >= pattern_min_percent:
                    patterns_to_remove[length].append((phrase, count, percentage))
        
        return patterns_to_remove
    
    def show_patterns_to_delete(self, patterns_to_remove: Dict) -> Dict[int, List[str]]:
        """Muestra patrones a eliminar y próximos (no eliminados) para validación"""
        print("\n" + "="*80)
        print("PATRONES A ELIMINAR")
        print("="*80)
        
        pattern_min_count = config.processing.pattern_min_count if config else 10
        pattern_min_percent = config.processing.pattern_min_percent if config else 5.0
        print(f"Criterios: Frecuencia >= {pattern_min_count} AND Porcentaje >= {pattern_min_percent}%\n")
        
        patterns_by_length = {1: [], 2: [], 3: []}
        
        for length in [3, 2, 1]:
            all_patterns = sorted(
                [(phrase, count, (count / self.total_observations) * 100) 
                 for phrase, count in self.patterns_by_length[length].items()],
                key=lambda x: x[1],
                reverse=True
            )
            
            if not all_patterns:
                continue
            
            print(f"--- PATRONES DE {length} PALABRA{'S' if length > 1 else ''} ---")
            print(f"{'#':<3} {'Frecuencia':<12} {'Porcentaje':<12} {'Frase':<50}")
            print("-" * 80)
            
            # Mostrar patrones a eliminar
            count_shown = 0
            for i, (phrase, count, percentage) in enumerate(all_patterns, 1):
                if count >= pattern_min_count and percentage >= pattern_min_percent:
                    print(f"{i:<3} {count:<12} {percentage:6.1f}%     {phrase:<50}")
                    patterns_by_length[length].append(phrase)
                    count_shown = i
            
            # Línea divisoria y patrones preservados
            if count_shown > 0 and count_shown < len(all_patterns):
                print("-" * 80)
                print(">>> Patrones siguientes que no se eliminan (no cumplen criterios) >>>")
                print("-" * 80)
                
                # Mostrar 2 siguientes que NO se eliminan
                shown_preserved = 0
                for i, (phrase, count, percentage) in enumerate(all_patterns[count_shown:], count_shown + 1):
                    if shown_preserved < 2:
                        print(f"{i:<3} {count:<12} {percentage:6.1f}%     {phrase:<50}")
                        shown_preserved += 1
            
            print()
        
        return patterns_by_length
    
    def clean_observation(self, text: str, patterns_to_remove: Dict[int, List[str]]) -> str:
        """Elimina patrones secuencialmente (3→2→1 palabras)"""
        cleaned_text = text.strip()
        
        for pattern in patterns_to_remove[3]:
            escaped_pattern = re.escape(pattern)
            regex_pattern = f"^{escaped_pattern}\\s*"
            cleaned_text = re.sub(regex_pattern, "", cleaned_text, flags=re.IGNORECASE)
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        for pattern in patterns_to_remove[2]:
            escaped_pattern = re.escape(pattern)
            regex_pattern = f"^{escaped_pattern}\\s*"
            cleaned_text = re.sub(regex_pattern, "", cleaned_text, flags=re.IGNORECASE)
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        for pattern in patterns_to_remove[1]:
            escaped_pattern = re.escape(pattern)
            regex_pattern = f"^{escaped_pattern}\\s*"
            cleaned_text = re.sub(regex_pattern, "", cleaned_text, flags=re.IGNORECASE)
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        if cleaned_text and not cleaned_text[0].isupper():
            cleaned_text = cleaned_text[0].upper() + cleaned_text[1:]
        
        return cleaned_text
    
    def generate_cleaned_file(self, patterns_to_remove: Dict[int, List[str]]) -> Tuple[int, Dict]:
        """Genera archivo Sprocesado_*.jsonl con estadísticas"""
        processed_file = self.paths['processed']
        output_file = processed_file.parent / f"S{processed_file.name}"
        
        cleaned_count = 0
        total_count = 0
        total_chars_before = 0
        total_chars_after = 0
        
        with open(processed_file, 'r', encoding='utf-8') as f_in:
            with open(output_file, 'w', encoding='utf-8') as f_out:
                for line in f_in:
                    try:
                        data = json.loads(line.strip())
                        total_count += 1
                        
                        if "messages" in data and len(data["messages"]) >= 2:
                            original_obs = data["messages"][1]["content"]
                            cleaned_obs = self.clean_observation(original_obs, patterns_to_remove)
                            
                            total_chars_before += len(original_obs)
                            total_chars_after += len(cleaned_obs)
                            
                            if original_obs != cleaned_obs:
                                cleaned_count += 1
                            
                            data["messages"][1]["content"] = cleaned_obs
                        
                        f_out.write(json.dumps(data, ensure_ascii=False) + '\n')
                    
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        print(f"Warning Error procesando línea: {e}")
                        continue
        
        avg_reduction_percent = (
            (total_chars_before - total_chars_after) / total_chars_before * 100
            if total_chars_before > 0 else 0
        )
        
        stats = {
            'total_processed': total_count,
            'total_cleaned': cleaned_count,
            'avg_reduction_percent': avg_reduction_percent,
            'patterns_removed_by_length': {
                1: len(patterns_to_remove[1]),
                2: len(patterns_to_remove[2]),
                3: len(patterns_to_remove[3])
            }
        }
        
        # Eliminar archivo procesado original
        try:
            if processed_file.exists():
                processed_file.unlink()
        except Exception as e:
            pass
        
        return cleaned_count, stats
    
    def run(self, auto_confirm: bool = True):
        """Ejecuta análisis y muestra patrones a eliminar"""
        self.analyze_patterns()
        patterns_to_remove = self.display_patterns()
        patterns_by_length = self.show_patterns_to_delete(patterns_to_remove)
        
        cleaned_count, stats = self.generate_cleaned_file(patterns_by_length)
        
        print("_"*80)
        print(f"ESTADISTICAS DE REDUCCION:")
        print("_"*80)
        print(f"   Registros procesados: {stats['total_processed']}")
        print(f"   Registros modificados: {stats['total_cleaned']} ({(stats['total_cleaned']/stats['total_processed']*100):.1f}%)")
        print(f"   Reduccion de caracteres: {stats['avg_reduction_percent']:.1f}%")
        print("_"*80+"\n"+"\n"+"\n")


def main():
    """Punto de entrada del script"""
    dataset_name = config.default_dataset_name if config else 'Datos_Mayo(2)'
    
    print("\n" + "="*80)
    print("SCRIPT 2: ANALIZADOR Y LIMPIADOR DE PATRONES")
    print("="*80)
    print(f"Dataset configurado: {dataset_name}")
    
    respuesta = input("\n¿Es este el dataset a procesar? (Y/N): ").strip().upper()
    
    if respuesta in ['N', 'NO']:
        dataset_name = input("Ingresa el nombre del dataset: ").strip()
    
    paths = config.get_dataset_paths(dataset_name) if config else {}
    processed_file = paths.get('processed') if paths else None
    
    if not processed_file or not processed_file.exists():
        print(f"\nERROR: No se encuentra archivo procesado para dataset '{dataset_name}'")
        if processed_file:
            print(f"   Buscando: {processed_file}")
        print("\n   Archivos disponibles:")
        datasets_dir = Path("data/processed")
        for dataset_dir in datasets_dir.iterdir():
            if dataset_dir.is_dir():
                for file in dataset_dir.glob("procesado_*.jsonl"):
                    print(f"   - {file.parent.name}")
                    break
        return 1
    
    processor = PatternAnalyzerCleaner(dataset_name)
    processor.run()
    
    return 0


if __name__ == "__main__":
    main()
