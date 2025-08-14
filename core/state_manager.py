import os
import networkx as nx
import re
from typing import Dict, Any

class StateManager:
    """
    Gestiona el estado de las variables y el grafo de dependencias de los scripts.
    """
    def __init__(self, registry: Dict[str, Dict[str, Any]]):
        self.registry = registry
        self.data: Dict[str, Any] = {}
        self.variable_sources: Dict[str, str] = {}
        self.script_states: Dict[str, str] = {path: 'idle' for path in registry.keys()}
        self.graph = self._build_dependency_graph()

    def _build_dependency_graph(self):
        """
        Construye el grafo de dependencias de scripts.
        """
        G = nx.DiGraph()
        for path, meta in self.registry.items():
            G.add_node(path, name=os.path.basename(path), produces=meta["produces"], requires=meta["requires"])

        # Crear un mapa de qué script produce cada variable
        var_producers = {}
        for path, meta in self.registry.items():
            for var in meta["produces"]:
                var_producers.setdefault(var, []).append(path)

        # Añadir aristas al grafo basándose en las dependencias de las variables
        for path, meta in self.registry.items():
            consumer_path = path
            for var in meta["requires"]:
                producers = var_producers.get(var, [])
                for p_path in producers:
                    G.add_edge(p_path, consumer_path, var=var)
        
        return G

    def get_missing_dependencies(self, script_path: str) -> list:
        """
        Devuelve una lista de variables requeridas que no están en el estado actual.
        """
        meta = self.registry.get(script_path)
        if not meta:
            return []
        
        missing_vars = [var for var in meta["requires"] if var not in self.data]
        return missing_vars

    def reset_state(self):
        """
        Reinicia el estado de todas las variables y scripts.
        """
        self.data.clear()
        self.variable_sources.clear()
        for path in self.script_states:
            self.script_states[path] = 'idle'

    def get_source_script(self, var_name: str) -> str:
        """
        Devuelve el path del script que produjo una variable.
        """
        return self.variable_sources.get(var_name, "Desconocido")
    
    def check_dependencies_and_run(self, script_path, runner, main_window, stop_at_produces=False, force_run=False):
        """
        Verifica las dependencias y ejecuta el script si se cumplen.
        """
        missing_dependencies = self.get_missing_dependencies(script_path)
        
        if missing_dependencies and not force_run:
            main_window.statusBar().showMessage(f"Faltan variables para '{os.path.basename(script_path)}': {missing_dependencies}. Buscando scripts...", 5000)
            
            # Buscar scripts que puedan producir las variables faltantes
            runnable_dependencies = []
            for pred_path, _, data in self.graph.in_edges(script_path, data=True):
                if data['var'] in missing_dependencies and self.script_states[pred_path] == 'idle':
                    runnable_dependencies.append(pred_path)
            
            if runnable_dependencies:
                for pred_path in runnable_dependencies:
                    # Ejecutar recursivamente los predecesores
                    self.check_dependencies_and_run(pred_path, runner, main_window)
            else:
                main_window.statusBar().showMessage(f"No se encontraron scripts para resolver todas las dependencias.", 5000)
                main_window.scriptStateChanged.emit(script_path, 'error')
                return
        
        # Si no hay dependencias faltantes o se fuerza la ejecución, correr el script actual
        self._run_script_internal(script_path, runner, main_window, stop_at_produces)
    
    def _run_script_internal(self, script_path, runner, main_window, stop_at_produces):
        """
        Lógica interna para ejecutar un solo script.
        """
        main_window.scriptStateChanged.emit(script_path, 'running')
        
        script_name = os.path.basename(script_path)
        print(f"Iniciando ejecución de '{script_name}'...")
        
        input_vars = {var: self.data[var] for var in self.registry[script_path]["requires"] if var in self.data}
        
        # CORRECCIÓN: Pasar el argumento correcto
        produced_data, output, error = runner.run_script(script_path, input_vars, stop_at_produces=stop_at_produces)
        
        print(f"--- Script '{script_name}' Output ---")
        print(output)
        
        if error:
            print(f"--- ERROR en '{script_name}' ---")
            print(error)
            print(f"No se pudo ejecutar el script '{script_name}'. Deteniendo la cadena de ejecución.")
            main_window.scriptStateChanged.emit(script_path, 'error')
            return
        
        for var_name, var_value in produced_data.items():
            self.data[var_name] = var_value
            self.variable_sources[var_name] = script_path
        
        # Verificar si la ejecución se detuvo parcialmente
        if "ORCHESTRATOR_PARTIAL_STOP" in output:
            print(f"--- Ejecución parcial de '{script_name}' finalizada. Se cargaron variables en memoria. ---")
            main_window.scriptStateChanged.emit(script_path, 'partial_finished')
        else:
            print(f"--- Script '{script_name}' ejecutado con éxito. ---")
            main_window.scriptStateChanged.emit(script_path, 'finished')

