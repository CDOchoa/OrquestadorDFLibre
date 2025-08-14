import os
import re
from typing import Dict, Any

def discover_scripts(directory: str) -> Dict[str, Dict[str, Any]]:
    """
    Escanea un directorio y sus subdirectorios para encontrar scripts de Python.
    Extrae metadatos (docstring, REQUIRES, PRODUCE) de cada script.
    """
    registry = {}
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        source_code = f.read()
                        
                        produces = []
                        requires = []
                        docstring = ""
                        
                        # Extraer metadatos de los comentarios
                        produces_matches = re.findall(r"#\s*ORCHESTRATOR\.PRODUCE:\s*([A-Za-z0-9_, ]+)", source_code)
                        requires_matches = re.findall(r"#\s*ORCHESTRATOR\.REQUIRES:\s*([A-Za-z0-9_, ]+)", source_code)
                        
                        for match in produces_matches:
                            produces.extend([var.strip() for var in match.split(',')])
                        for match in requires_matches:
                            requires.extend([var.strip() for var in match.split(',')])
                            
                        # Extraer docstring
                        docstring_match = re.search(r'"""(.*?)"""', source_code, re.DOTALL)
                        if docstring_match:
                            docstring = docstring_match.group(1).strip()
                            
                        registry[path] = {
                            "source_code": source_code,
                            "produces": produces,
                            "requires": requires,
                            "docstring": docstring,
                            "name": file
                        }
                except Exception as e:
                    print(f"Error al procesar el script {path}: {e}")
                    
    return registry

