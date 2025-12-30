#!/usr/bin/env python3
"""
PROMPT VERSION MANAGER - Seleccionador de versiones de prompts
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
from .versions import KnowledgeBaseV3


class PromptManager:
    """Gestor de versiones de prompts"""

    def __init__(self):
        self.current_version = None
        self._loaded_kb = None

    AVAILABLE_VERSIONS = {
        "3": {
            "name": "v3",
            "description": "Versión de ejemplo simplificada (PÚBLICA GITHUB)",
            "class": KnowledgeBaseV3,
            "released": "2025-12-29",
            "changes": ["Versión de demostración con 3 delitos y 3 reglas básicas"]
        }
    }
    
    def get_available_versions(self) -> Dict:
        """Retorna información de todas las versiones disponibles"""
        return self.AVAILABLE_VERSIONS
    
    def get_version_info(self, version: str) -> Dict:
        """Obtiene información detallada de una versión específica"""
        if version not in self.AVAILABLE_VERSIONS:
            raise ValueError(f"Versión '{version}' no encontrada. Disponibles: {list(self.AVAILABLE_VERSIONS.keys())}")
        return self.AVAILABLE_VERSIONS[version]
    
    def load_version(self, version: str = "3") -> object:
        """Carga y retorna la KnowledgeBase de una versión específica"""
        if version not in self.AVAILABLE_VERSIONS:
            raise ValueError(f"Versión '{version}' no encontrada. Disponibles: {list(self.AVAILABLE_VERSIONS.keys())}")
        
        version_info = self.AVAILABLE_VERSIONS[version]
        self.current_version = version
        self._loaded_kb = version_info["class"]()
        
        return self._loaded_kb
    
    def switch_version(self, version: str) -> object:
        """Alias de load_version"""
        return self.load_version(version)
    
    def get_current_version(self) -> str:
        """Retorna la versión actualmente cargada"""
        return self.current_version
    
    def get_current_kb(self) -> Optional[object]:
        """Retorna la KnowledgeBase actualmente cargada"""
        if self._loaded_kb is None:
            self._loaded_kb = self.load_version(self.current_version)
        return self._loaded_kb
    
    def print_versions_summary(self):
        """Imprime un resumen de las versiones disponibles"""
        print("\n" + "="*70)
        print("VERSIONES DE PROMPTS DISPONIBLES")
        print("="*70 + "\n")
        
        for version_key, version_info in self.AVAILABLE_VERSIONS.items():
            print(f"📌 VERSIÓN {version_key}: {version_info['name']}")
            print(f"   Descripción: {version_info['description']}")
            print(f"   Lanzamiento: {version_info['released']}")
            print(f"   Cambios:")
            for change in version_info['changes']:
                print(f"     • {change}")
            print()
    
    def list_versions(self) -> List[str]:
        """Retorna lista de versiones disponibles"""
        return list(self.AVAILABLE_VERSIONS.keys())


def get_prompt_manager() -> PromptManager:
    """Retorna instancia del PromptManager"""
    return PromptManager()


def get_knowledge_base(version: str = "3") -> object:
    """Función de conveniencia para obtener directamente una KnowledgeBase"""
    manager = PromptManager()
    return manager.load_version(version)


def get_validation_prompt(observacion: str, version: str = "3") -> Tuple[str, str]:
    """Genera prompts de sistema y usuario para una observación"""
    kb = get_knowledge_base(version)
    return kb.get_validation_prompt(observacion)


# Compatibilidad hacia atrás
KnowledgeBase = KnowledgeBaseV3

if __name__ == "__main__":
    manager = PromptManager()
    manager.print_versions_summary()
    
    kb = manager.load_version("3")
    print(f"\n✓ Versión {manager.get_current_version()} cargada correctamente")
    print(f"  Descripción: {manager.get_version_info(manager.get_current_version())['description']}")
