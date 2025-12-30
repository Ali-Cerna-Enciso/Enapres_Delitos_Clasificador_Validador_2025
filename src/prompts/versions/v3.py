#!/usr/bin/env python3
"""
VERSIÓN 3 - Base de conocimiento EJEMPLO para clasificación de delitos
NOTA: Esta es una versión de ejemplo simplificada para demostración.
No contiene la base de conocimiento completa.

Fecha: 2025-12-29
"""

import json
from typing import Dict, List, Tuple


class DelitoDefinitions:
    """Definiciones de códigos de delito (EJEMPLO - Solo 3 delitos)"""
    
    DEFINITIONS = {
        "9": "Robo de efectos personales (celular, cartera, dinero, mochila)",
        "23": "Fraude bancario (uso no autorizado de cuentas/tarjetas)",
        "2": "Intento de robo de vehículo automotor (auto, camioneta, etc.)",
    }


class PromptRules:
    """Reglas para clasificación (EJEMPLO - Solo 3 reglas básicas)"""
    
    CORE_RULES = [
        "PERIODO DE REFERENCIA: El hecho debe haber ocurrido en los 'ÚLTIMOS 12 MESES'. Si es más antiguo, IGNORAR.",
        "PRINCIPIO DE SUFICIENCIA: Si la observación es ambigua sin explicar el HECHO, NO clasificar.",
        "NO ASUMIR DATOS: Prohibido asumir fechas, parentescos o ubicaciones no escritas. Si no dice explícitamente que viven juntos, NO asumas convivencia",
    ]
    
    EXAMPLES = [
        {
            "observacion": "Me robaron mi celular en la calle cuando iba caminando, me lo arrebataron y se fueron corriendo.",
            "razonamiento": "1. Identifico un incidente: robo de celular consumado. 2. Le sustrajeron el celular personalmente. 3. Clasifico como código 9 (robo de efectos personales). 4. Construyo el JSON.",
            "clasificaciones": [
                {"codigo": "9", "justificacion": "Robo consumado de celular arrebatado en la calle."}
            ]
        }
    ]


class KnowledgeBase:
    """Base de conocimiento EJEMPLO para clasificación de delitos ENAPRES"""
    
    def __init__(self):
        self.definitions = DelitoDefinitions.DEFINITIONS
        self.rules = PromptRules.CORE_RULES
        self.examples = PromptRules.EXAMPLES
    
    def get_system_prompt(self) -> str:
        """Genera el prompt de sistema con la base de conocimiento"""
        
        definitions_text = "\n".join([
            f"- {code}: {desc}" 
            for code, desc in self.definitions.items()
        ])
        
        rules_text = "\n".join([f"{i+1}. {rule}" for i, rule in enumerate(self.rules)])
        
        examples_text = ""
        for i, ex in enumerate(self.examples, 1):
            ex_json = json.dumps(ex["clasificaciones"], indent=2, ensure_ascii=False)
            examples_text += f"\n### Ejemplo {i}\n"
            examples_text += f"**Observación:** {ex['observacion']}\n\n"
            examples_text += f"**Razonamiento:** {ex['razonamiento']}\n\n"
            examples_text += f"**Salida JSON:**\n```json\n{ex_json}\n```\n"
        
        system_prompt = f"""Eres un clasificador de delitos para la encuesta ENAPRES (EJEMPLO).

NOTA: Esta es una versión de ejemplo simplificada para demostración.

# CÓDIGOS DE DELITO (EJEMPLO)
{definitions_text}

# REGLAS DE CLASIFICACIÓN (EJEMPLO)
{rules_text}

# EJEMPLOS DE CLASIFICACIÓN
{examples_text}

# FORMATO DE SALIDA
Responde ÚNICAMENTE con un JSON válido en este formato:
```json
[
  {{"codigo": "9", "justificacion": "Descripción del delito"}},
  {{"codigo": "21", "justificacion": "Descripción del delito"}}
]
```

Si NO hay delitos clasificables, responde: []
"""
        return system_prompt
    
    def get_user_prompt(self, observacion: str) -> str:
        """Genera el prompt del usuario con la observación a clasificar"""
        return f"""Clasifica los delitos en esta observación:

{observacion}

Responde SOLO con el JSON de clasificación."""
    
    def get_validation_prompt(self, observacion: str) -> Tuple[str, str]:
        """Retorna tupla (system_prompt, user_prompt)"""
        return (self.get_system_prompt(), self.get_user_prompt(observacion))
