"""
Analiza un script Python y extrae:
- PRODUCES (lista)
- REQUIRES (lista)
- docstring
- código fuente
"""

import ast
from pathlib import Path
from typing import Dict, Any

def parse_script(path: str) -> Dict[str, Any]:
    """
    Devuelve dict:
    {
      "path": str,
      "name": "script_a.py",
      "produces": [...],
      "requires": [...],
      "docstring": "...",
      "source_code": "..."
    }
    """
    p = Path(path)
    source = p.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(p))

    produces = []
    requires = []
    doc = ast.get_docstring(tree)

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id
                    if name in ("PRODUCES", "REQUIRES"):
                        try:
                            value = ast.literal_eval(node.value)
                            if isinstance(value, (list, tuple)):
                                if name == "PRODUCES":
                                    produces = list(map(str, value))
                                else:
                                    requires = list(map(str, value))
                        except Exception:
                            pass

    return {
        "path": str(p.resolve()),
        "name": p.name,
        "produces": produces,
        "requires": requires,
        "docstring": doc or "",
        "source_code": source
    }