"""
Versiones de prompts para clasificación de delitos ENAPRES

Cada versión contiene:
- Definiciones de códigos
- Reglas de clasificación
- Ejemplos de referencia
"""

from .v3 import KnowledgeBase as KnowledgeBaseV3

__all__ = ["KnowledgeBaseV3"]
