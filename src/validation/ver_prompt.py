#!/usr/bin/env python3
"""
Script para visualizar el prompt completo que se envía a la API
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.prompts.crime_validation_prompts import get_knowledge_base
from src.config.config_manager import config

def generate_example_response(observacion):
    """Genera una respuesta de ejemplo que la IA podría dar"""
    respuesta = f"""ANÁLISIS DE VALIDACIÓN:

Observación Original:
"{observacion}"

VALIDACIÓN REALIZADA:
✓ Tipo de Delito Identificado: ROBO
✓ Código de Delito: 210100 - Hurto/Robo
✓ Bien Afectado: Equipos electrónicos (celular, laptop)
✓ Lugar del Hecho: Vía pública
✓ Mes del Incidente: Agosto (según informante)

CLASIFICACIÓN FINAL:
- Delito: SI, es un delito
- Categoría: Crimen contra la propiedad
- Severidad: Moderada
- Estado: VALIDADO

OBSERVACIONES:
- La descripción contiene elementos claros de un robo
- Se menciona específicamente los bienes sustraídos (celular y laptop)
- La ubicación en la calle indica que fue en vía pública
- Hay mención de la persona afectada (informante)
- Fecha aproximada: Agosto (información proporcionada)

RECOMENDACIÓN: 
Registro puede ser procesado como un delito válido. Sugerir registrar en base de datos con código 210100."""
    return respuesta

def main():
    # Crear instancia de la base de conocimiento desde config
    prompt_version = config.get_prompts_version()
    kb = get_knowledge_base(version=prompt_version)
    
    # Ejemplo de observación (puedes cambiarla)
    observacion_ejemplo = "ROBO DE CELULAR EN LA CALLE. INFORMANTE MENCIONA QUE LE ROBARON SU MOCHILA CON LAPTOP EN AGOSTO."
    
    # Obtener los prompts
    system_prompt, user_prompt = kb.get_validation_prompt(observacion_ejemplo)
    
    # Generar respuesta de ejemplo
    respuesta_ejemplo = generate_example_response(observacion_ejemplo)
    
    # Mostrar el prompt del sistema
    print("=" * 100)
    print("PROMPT DEL SISTEMA (System Prompt)")
    print("=" * 100)
    print(system_prompt)
    print("\n" * 2)
    
    # Mostrar el prompt del usuario
    print("=" * 100)
    print("PROMPT DEL USUARIO (User Prompt)")
    print("=" * 100)
    print(user_prompt)
    print("\n" * 2)
    
    # Mostrar la respuesta de ejemplo
    print("=" * 100)
    print("RESPUESTA DE EJEMPLO DE LA IA")
    print("=" * 100)
    print(respuesta_ejemplo)
    print("\n" * 2)
    
    # Estadísticas
    print("=" * 100)
    print("ESTADÍSTICAS DEL PROMPT")
    print("=" * 100)
    print(f"Longitud System Prompt: {len(system_prompt)} caracteres")
    print(f"Longitud User Prompt: {len(user_prompt)} caracteres")
    print(f"Total: {len(system_prompt) + len(user_prompt)} caracteres")
    print(f"Total palabras (aprox): {(len(system_prompt) + len(user_prompt)) // 5}")
    print()
    print(f"Número de reglas: {len(kb.rules)}")
    print(f"Número de códigos: {len(kb.definitions)}")
    print(f"Número de ejemplos: {len(kb.examples)}")
    print("=" * 100)
    
    # Guardar en archivo de texto
    output_file = Path("prompt_completo.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        # ENCABEZADO INICIAL
        f.write("╔" + "═" * 98 + "╗\n")
        f.write("║" + " " * 20 + "DOCUMENTACIÓN DE VALIDACIÓN DE DELITOS - FLUJO DE IA" + " " * 28 + "║\n")
        f.write("╚" + "═" * 98 + "╝\n")
        f.write("\n")
        f.write("DESCRIPCIÓN DEL DOCUMENTO:\n")
        f.write("-" * 100 + "\n")
        f.write("Este documento muestra el flujo completo de validación de delitos mediante IA.\n")
        f.write("Está dividido en 2 partes principales:\n")
        f.write("  • PARTE 1: ENTRADA DE LA IA - Todo lo que entra al sistema (instrucciones + datos)\n")
        f.write("  • PARTE 2: SALIDA DE LA IA - Respuesta que genera el sistema (validación)\n")
        f.write("\nEste flujo permite verificar consistencia entre lo que se ingresa y lo que se obtiene.\n")
        f.write("=" * 100 + "\n")
        f.write("\n\n")
        
        # PARTE 1: ENTRADA DE LA IA
        f.write("╔" + "═" * 98 + "╗\n")
        f.write("║" + " " * 35 + "PARTE 1: ENTRADA DE LA IA" + " " * 37 + "║\n")
        f.write("╚" + "═" * 98 + "╝\n")
        f.write("\n\n")
        
        f.write("OBSERVACIÓN A VALIDAR:\n")
        f.write("-" * 100 + "\n")
        f.write(f'"{observacion_ejemplo}"\n')
        f.write("\n\n")
        
        f.write("=" * 100 + "\n")
        f.write("INSTRUCCIONES DEL SISTEMA\n")
        f.write("=" * 100 + "\n")
        f.write(system_prompt)
        f.write("\n\n\n")
        
        f.write("=" * 100 + "\n")
        f.write("DATOS A PROCESAR\n")
        f.write("=" * 100 + "\n")
        f.write(user_prompt)
        f.write("\n\n\n")
        
        f.write("=" * 100 + "\n")
        f.write("ESTADÍSTICAS DEL ENTRADA\n")
        f.write("=" * 100 + "\n")
        f.write(f"Longitud Instrucciones: {len(system_prompt)} caracteres\n")
        f.write(f"Longitud Datos: {len(user_prompt)} caracteres\n")
        f.write(f"Total Entrada: {len(system_prompt) + len(user_prompt)} caracteres\n")
        f.write(f"Total palabras (aprox): {(len(system_prompt) + len(user_prompt)) // 5}\n")
        f.write(f"\nComponentes del sistema:\n")
        f.write(f"  - Número de reglas: {len(kb.rules)}\n")
        f.write(f"  - Número de códigos de delito: {len(kb.definitions)}\n")
        f.write(f"  - Número de ejemplos: {len(kb.examples)}\n")
        f.write("\n\n\n")
        
        # PARTE 2: SALIDA DE LA IA
        f.write("╔" + "═" * 98 + "╗\n")
        f.write("║" + " " * 36 + "PARTE 2: SALIDA DE LA IA" + " " * 38 + "║\n")
        f.write("╚" + "═" * 98 + "╝\n")
        f.write("\n\n")
        f.write("VALIDACIÓN Y RESPUESTA DEL SISTEMA:\n")
        f.write("-" * 100 + "\n\n")
        f.write(respuesta_ejemplo)
        f.write("\n\n")
    
    print(f"\n✅ Documento completo guardado en: {output_file}")
    print(f"\n   Estructura del documento:")
    print(f"   ├─ ENCABEZADO: Descripción del flujo (Entrada vs Salida)")
    print(f"   ├─ PARTE 1: ENTRADA DE LA IA")
    print(f"   │  ├─ Observación a validar")
    print(f"   │  ├─ Instrucciones del sistema")
    print(f"   │  ├─ Datos a procesar")
    print(f"   │  └─ Estadísticas")
    print(f"   └─ PARTE 2: SALIDA DE LA IA")
    print(f"      └─ Validación y respuesta del sistema")

if __name__ == "__main__":
    main()

