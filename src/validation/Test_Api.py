#!/usr/bin/env python3
"""
Validador de API para clasificación de delitos.
Soporta modo interactivo, múltiples proveedores y análisis de consistencia.
"""

import os
import asyncio
import json
import sys
from openai import AsyncOpenAI, AuthenticationError
from pathlib import Path

# IMPORTANTE: Cargar .env explícitamente ANTES de importar config
from dotenv import load_dotenv
env_file = Path(__file__).resolve().parents[2] / ".env"
if env_file.exists():
    load_dotenv(env_file, override=True)

# Agregar el directorio raíz del proyecto al path de Python
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

try:
    from src.config.config_manager import config
    from src.prompts.crime_validation_prompts import get_knowledge_base
except Exception:
    config = None
    from prompts.crime_validation_prompts import get_knowledge_base


# ============================================================================
# CONFIGURACIÓN DE API
# ============================================================================

API_PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY"
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4",
        "env_key": "OPENAI_API_KEY"
    }
}

DEFAULT_PROVIDER = "deepseek"


# ============================================================================
# FUNCIONES DE PRUEBA
# ============================================================================

async def probar_clasificacion_delitos(observacion: str, provider: str = DEFAULT_PROVIDER, intento_num: int = 1, total_intentos: int = 1):
    """
    Prueba la clasificación de delitos vía API.
    
    Args:
        observacion: Texto de la observación a clasificar
        provider: Proveedor de API
        intento_num: Número del intento actual (para títulos)
        total_intentos: Total de intentos (para títulos)
    """
    print("="*120)
    if total_intentos > 1:
        print(f"INTENTO {intento_num}/{total_intentos} - CLASIFICACIÓN DE DELITOS - {provider.upper()}")
    else:
        print(f"PRUEBA DE CLASIFICACIÓN - {provider.upper()}")
    print("="*120)
    
    # Validar proveedor
    if provider not in API_PROVIDERS:
        print(f"❌ ERROR: Proveedor '{provider}' no soportado")
        print(f"   Disponibles: {', '.join(API_PROVIDERS.keys())}")
        return None
    
    provider_config = API_PROVIDERS[provider]
    api_key = os.environ.get(provider_config["env_key"])
    
    # Verificar API key
    if not api_key:
        print(f"❌ ERROR: Variable '{provider_config['env_key']}' no encontrada")
        print(f"   Configúrala: $env:{provider_config['env_key']}=\"tu_clave\"")
        return None
    
    print(f"API Key: ...{api_key[-6:]}")
    
    # Mostrar versión de prompts
    if config:
        prompt_version = config.get_prompts_version()
        print(f"Versión de prompts: {prompt_version}")
    else:
        prompt_version = "1"
        print("⚠️  Config no disponible, usando versión por defecto: 1")
    
    print(f"\nObservación:")
    print("-" * 120)
    print(observacion)  # Mostrar COMPLETO sin truncar
    print("-" * 120)
    
    # Preparar prompts
    try:
        knowledge_base = get_knowledge_base(version=prompt_version)
    except Exception as e:
        print(f"⚠️  Error cargando versión {prompt_version}: {e}, usando v1")
        knowledge_base = get_knowledge_base(version="1")
    
    system_prompt, user_prompt = knowledge_base.get_validation_prompt(observacion)
    client = AsyncOpenAI(api_key=api_key, base_url=provider_config["base_url"])
    
    # Llamar API
    try:
        print(f"\nEnviando a {provider.upper()}...")
        
        response = await client.chat.completions.create(
            model=provider_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=2000,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        print("✅ Respuesta recibida")
        
        # PROCESAMIENTO: Convertir respuesta de texto a objeto Python
        respuesta_texto = response.choices[0].message.content
        print("\nRespuesta COMPLETA:")
        print("-" * 120)
        print(respuesta_texto)  # Mostrar COMPLETO sin truncar
        print("-" * 120)
        
        try:
            # 1. CONVERSIÓN JSON: Convertir string JSON a diccionario Python
            resultado_json = json.loads(respuesta_texto.strip())
            
            print("\n✅ JSON válido")
            print("\nDelitos identificados:")
            
            # 2. EXTRACCIÓN: Obtener lista de clasificaciones del diccionario
            clasificaciones = resultado_json.get('clasificaciones', [])
            codigos_encontrados = []
            
            if clasificaciones:
                for i, clasificacion in enumerate(clasificaciones, 1):
                    codigo = clasificacion.get('codigo', 'N/A')
                    justificacion = clasificacion.get('justificacion', 'Sin descripción')
                    print(f"  {i}. Código {codigo}")
                    print(f"     └─ {justificacion}")
                    codigos_encontrados.append(codigo)
            else:
                print("  ✓ Ningún delito identificado")
            
            # 3. RESULTADO: Agregar códigos al resultado para comparación
            resultado_json['codigos_extraidos'] = sorted(codigos_encontrados)
            
            return resultado_json
            
        except json.JSONDecodeError as e:
            print(f"\n❌ Error parseando JSON: {e}")
            print(f"Respuesta raw: {respuesta_texto}")
            return None
    
    except AuthenticationError:
        print(f"\n❌ ERROR DE AUTENTICACIÓN: API key inválida")
        print(f"   Regenera la clave para {provider}")
        return None
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return None


def calcular_similitud_resultados(resultados):
    """
    Calcula la similitud entre múltiples resultados de clasificación.
    
    Args:
        resultados: Lista de diccionarios con resultados de clasificación
    
    Returns:
        Dict con estadísticas de similitud
    """
    if len(resultados) < 2:
        return {"similitud": 100.0, "mensaje": "Solo un resultado, no hay comparación"}
    
    # Extraer conjuntos de códigos de cada resultado
    todos_codigos = []
    for resultado in resultados:
        if resultado and 'codigos_extraidos' in resultado:
            codigos = set(resultado['codigos_extraidos'])
            todos_codigos.append(codigos)
    
    if not todos_codigos:
        return {"similitud": 0.0, "mensaje": "No se pudieron extraer códigos"}
    
    # Encontrar códigos comunes a TODOS los resultados (intersección)
    codigos_comunes = set.intersection(*todos_codigos) if todos_codigos else set()
    
    # Encontrar códigos que aparecieron en CUALQUIER resultado (unión)
    todos_codigos_unicos = set.union(*todos_codigos) if todos_codigos else set()
    
    # Calcular similitud: códigos comunes / total de códigos únicos
    if len(todos_codigos_unicos) == 0:
        similitud = 100.0 if len(codigos_comunes) == 0 else 0.0
    else:
        similitud = (len(codigos_comunes) / len(todos_codigos_unicos)) * 100
    
    # Contar frecuencia de cada código
    conteo_codigos = {}
    for codigos in todos_codigos:
        for codigo in codigos:
            conteo_codigos[codigo] = conteo_codigos.get(codigo, 0) + 1
    
    return {
        "similitud": similitud,
        "total_intentos": len(resultados),
        "codigos_comunes": sorted(list(codigos_comunes)),
        "codigos_unicos": sorted(list(todos_codigos_unicos)),
        "conteo_por_codigo": conteo_codigos,
        "mensaje": f"Similitud: {similitud:.1f}%"
    }


def mostrar_resumen_similitud(stats_similitud):
    """Muestra un resumen visual de la similitud entre resultados."""
    print("\n" + "🔍 ANÁLISIS DE SIMILITUD".center(120, "="))
    print(f"Total de intentos: {stats_similitud['total_intentos']}")
    print(f"Similitud general: {stats_similitud['similitud']:.1f}%")
    
    if stats_similitud['similitud'] == 100.0:
        print("✅ RESULTADO PERFECTO: Todos los intentos produjeron exactamente los mismos códigos")
    elif stats_similitud['similitud'] >= 80.0:
        print("✅ ALTA CONSISTENCIA: La mayoría de códigos coinciden")
    elif stats_similitud['similitud'] >= 50.0:
        print("⚠️  CONSISTENCIA MEDIA: Algunos códigos coinciden")
    else:
        print("❌ BAJA CONSISTENCIA: Pocos códigos coinciden entre intentos")
    
    print("\n📊 CÓDIGOS IDENTIFICADOS:")
    conteo = stats_similitud.get('conteo_por_codigo', {})
    total_intentos = stats_similitud['total_intentos']
    
    for codigo in sorted(conteo.keys()):
        frecuencia = conteo[codigo]
        porcentaje = (frecuencia / total_intentos) * 100
        if frecuencia == total_intentos:
            print(f"  ✅ Código {codigo}: {frecuencia}/{total_intentos} intentos ({porcentaje:.0f}%) - CONSISTENTE")
        elif frecuencia >= total_intentos * 0.5:
            print(f"  ⚠️  Código {codigo}: {frecuencia}/{total_intentos} intentos ({porcentaje:.0f}%) - PARCIAL")
        else:
            print(f"  ❌ Código {codigo}: {frecuencia}/{total_intentos} intentos ({porcentaje:.0f}%) - INCONSISTENTE")
    
    if stats_similitud['codigos_comunes']:
        print(f"\n🎯 CÓDIGOS EN TODOS LOS INTENTOS: {', '.join(stats_similitud['codigos_comunes'])}")
    else:
        print("\n⚠️  NO HAY CÓDIGOS COMUNES EN TODOS LOS INTENTOS")
    
    print("=" * 120)


async def modo_interactivo(provider: str = DEFAULT_PROVIDER):
    print("\n" + "="*120)
    print(f"MODO INTERACTIVO - {provider.upper()}")
    print("="*120)
    print("Escribe 'salir' para terminar")
    print("-"*120)
    
    while True:
        print("\n" + "-"*50)
        try:
            observacion = input("Observación: ").strip()
        except EOFError:
            print("Sin entrada disponible, finalizando...")
            break
        
        if observacion.lower() in ['salir', 'exit', 'quit']:
            print("¡Hasta luego!")
            break
        
        if not observacion:
            print("Ingresa una observación válida")
            continue
        
        # Preguntar cuántas veces comparar
        try:
            num_intentos = input("¿Cuántas veces enviar esta observación? [1]: ").strip()
            num_intentos = int(num_intentos) if num_intentos else 1
            if num_intentos < 1:
                num_intentos = 1
        except ValueError:
            num_intentos = 1
        
        # Ejecutar múltiples intentos y almacenar resultados
        resultados = []
        for intento in range(1, num_intentos + 1):
            resultado = await probar_clasificacion_delitos(observacion, provider, intento, num_intentos)
            resultados.append(resultado)
            
            if intento < num_intentos:
                print("\n" + "="*120)
                print("Esperando antes del siguiente intento...")
                await asyncio.sleep(1)
        
        # Mostrar análisis de similitud si hay múltiples intentos
        if num_intentos > 1:
            stats = calcular_similitud_resultados(resultados)
            mostrar_resumen_similitud(stats)


async def modo_ejemplo(provider: str = DEFAULT_PROVIDER):
    ejemplo = "INFORMANTE INDICA QUE LE ROBARON SU CELULAR Y CARTERA EN LA CALLE. ADEMÁS, EN OTRO HECHO, RECIBIÓ UN BILLETE FALSO CUANDO VENDÍA EN SU NEGOCIO."
    
    print("\n" + "="*120)
    print(f"MODO EJEMPLO - {provider.upper()}")
    print("="*120)
    
    # Preguntar cuántas veces comparar
    try:
        num_intentos = input("¿Cuántas veces enviar este ejemplo? [1]: ").strip()
        num_intentos = int(num_intentos) if num_intentos else 1
        if num_intentos < 1:
            num_intentos = 1
    except ValueError:
        num_intentos = 1
    
    # Ejecutar múltiples intentos y almacenar resultados
    resultados = []
    for intento in range(1, num_intentos + 1):
        resultado = await probar_clasificacion_delitos(ejemplo, provider, intento, num_intentos)
        resultados.append(resultado)
        
        if intento < num_intentos:
            print("\n" + "="*120)
            print("Esperando antes del siguiente intento...")
            await asyncio.sleep(1)
    
    # Mostrar análisis de similitud si hay múltiples intentos
    if num_intentos > 1:
        stats = calcular_similitud_resultados(resultados)
        mostrar_resumen_similitud(stats)


async def test_simple():
    """Ejecución simple y directa sin menús interactivos"""
    print("🚀 PRUEBA SIMPLE - CLASIFICADOR DE DELITOS")
    print("="*60)
    
    # Usar configuración por defecto
    provider = DEFAULT_PROVIDER
    observacion = "Me robaron el celular y la billetera en la calle"
    
    # Mostrar configuración
    provider_config = API_PROVIDERS[provider]
    api_key = os.getenv(provider_config["env_key"])
    if not api_key:
        print(f"❌ ERROR: {provider_config['env_key']} no configurada")
        return
    
    print(f"✓ API Key: ...{api_key[-6:]}")
    if config:
        prompt_version = config.get_prompts_version()
        print(f"✓ Versión prompts: {prompt_version}")
    
    # Ejecutar prueba
    print(f"\nObservación: {observacion}")
    print("-" * 60)
    
    resultado = await probar_clasificacion_delitos(observacion, provider)
    return resultado


async def main():
    print("="*120)
    print("PRUEBA DE API - CLASIFICADOR DE DELITOS")
    print("="*120)
    
    # Mostrar versión de prompts configurada
    if config:
        prompt_version = config.get_prompts_version()
        print(f"✓ Versión de prompts configurada: {prompt_version}")
    else:
        print("⚠️  Config no disponible")
    
    # Seleccionar proveedor
    print("\nProveedores disponibles:")
    for i, (key, val) in enumerate(API_PROVIDERS.items(), 1):
        print(f"  {i}. {key.upper()} ({val['model']})")
    
    provider = DEFAULT_PROVIDER
    try:
        opcion = input(f"\nProveedor (1-{len(API_PROVIDERS)}) [Enter = {DEFAULT_PROVIDER.upper()}]: ").strip()
        if opcion:
            try:
                idx = int(opcion) - 1
                provider_list = list(API_PROVIDERS.keys())
                if 0 <= idx < len(provider_list):
                    provider = provider_list[idx]
                else:
                    print(f"⚠️  Opción inválida. Usando {DEFAULT_PROVIDER.upper()}")
            except ValueError:
                print(f"⚠️  Ingreso inválido. Usando {DEFAULT_PROVIDER.upper()}")
    except EOFError:
        print(f"Sin entrada disponible, usando {DEFAULT_PROVIDER.upper()}")
    
    # Seleccionar modo
    print(f"\nModos:")
    print(f"  1. Interactivo (con opción de comparar respuestas)")
    print(f"  2. Ejemplo (con opción de comparar respuestas)")
    print(f"  3. Prueba simple")
    print(f"  4. Ejecución directa (sin menús)")
    
    try:
        modo = input("\nModo (1-4) [Enter = 4]: ").strip()
        
        if modo == "1":
            await modo_interactivo(provider)
        elif modo == "2":
            await modo_ejemplo(provider)
        elif modo == "3":
            await probar_clasificacion_delitos("Me robaron el celular", provider)
        elif modo == "4" or not modo:
            await test_simple()
        else:
            print("Opción inválida")
    
    except KeyboardInterrupt:
        print("\n\nInterrumpido")
    except EOFError:
        print("Sin entrada disponible, ejecutando modo directo...")
        await test_simple()
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
