import pandas as pd
import pickle
import os
import networkx as nx
import importlib.util

class StateManager:
    def __init__(self, registry):
        self.registry = registry
        self.data = self.load_state_data()
        self.script_states = {}
        self.graph = nx.DiGraph()
        
        self.update_states_from_registry()

    def update_states_from_registry(self):
        """Inicializa y actualiza el diccionario script_states basado en el registro."""
        for path in self.registry.keys():
            if path not in self.script_states:
                self.script_states[path] = 'idle'
        
        paths_to_remove = [path for path in self.script_states.keys() if path not in self.registry]
        for path in paths_to_remove:
            del self.script_states[path]

    def reset_state(self):
        """Reinicia el estado de todos los scripts y limpia las variables almacenadas."""
        self.data.clear()
        for path in self.script_states:
            self.script_states[path] = 'idle'
        self.save_state_data()
    
    def get_source_script(self, var_name):
        """Encuentra el script que produjo una variable dada."""
        for path, meta in self.registry.items():
            if var_name in meta["produces"]:
                return path
        return None

    def load_state_data(self):
        """Carga las variables persistidas desde un archivo."""
        if os.path.exists("state.pkl"):
            try:
                with open("state.pkl", "rb") as f:
                    return pickle.load(f)
            except (IOError, pickle.PickleError):
                print("Error al cargar el archivo de estado. Se inicia con estado vacío.")
                return {}
        return {}

    def save_state_data(self):
        """Guarda las variables actuales en un archivo."""
        try:
            with open("state.pkl", "wb") as f:
                pickle.dump(self.data, f)
        except IOError:
            print("Error al guardar el archivo de estado.")

    def run_script_with_dependencies(self, script_path, runner, main_window, stop_at_produces, force_run=False):
        """
        Ejecuta un script y sus dependencias de forma recursiva.
        """
        if self.script_states[script_path] in ['finished', 'partial_finished'] and not force_run:
            print(f"Saltando {os.path.basename(script_path)}, ya se ejecutó.")
            return

        for pred_path in self.graph.predecessors(script_path):
            if pred_path in self.script_states:
                self.run_script_with_dependencies(pred_path, runner, main_window, False)
        
        required_vars = self.registry[script_path].get("requires", [])
        missing_vars = [var for var in required_vars if var not in self.data]
        if missing_vars:
            print(f"Faltan variables para {os.path.basename(script_path)}: {', '.join(missing_vars)}")
            main_window.scriptStateChanged.emit(script_path, 'error')
            return

        print(f"Ejecutando {os.path.basename(script_path)}...")
        main_window.scriptStateChanged.emit(script_path, 'running')
        
        try:
            # Ya no dependemos de que runner devuelva un diccionario.
            # Gestionamos la ejecución y captura de variables aquí.
            
            # Crear un espacio de nombres para las variables del script.
            # No es estrictamente necesario, pero es buena práctica.
            script_namespace = {}
            
            # Cargar el código del script
            with open(script_path, 'r', encoding='utf-8') as f:
                script_code = f.read()

            # Inyectar las variables requeridas en el espacio de nombres del script
            for var_name in required_vars:
                if var_name in self.data:
                    script_namespace[var_name] = self.data[var_name]

            # Ejecutar el código del script dentro del nuevo espacio de nombres
            exec(script_code, script_namespace)
            
            # Capturar las variables producidas por nombre desde el espacio de nombres del script
            produced_vars = {}
            for var_name in self.registry[script_path].get("produces", []):
                if var_name in script_namespace:
                    produced_vars[var_name] = script_namespace[var_name]
                else:
                    raise NameError(f"La variable '{var_name}' no se encontró en el script '{os.path.basename(script_path)}'.")
            
            self.data.update(produced_vars)
            self.save_state_data()
            
            if stop_at_produces:
                self.script_states[script_path] = 'partial_finished'
                print(f"Ejecución parcial de {os.path.basename(script_path)} finalizada, variables cargadas.")
            else:
                self.script_states[script_path] = 'finished'
                print(f"{os.path.basename(script_path)} finalizó correctamente.")
            
            main_window.scriptStateChanged.emit(script_path, self.script_states[script_path])
        
        except Exception as e:
            print(f"Error ejecutando {os.path.basename(script_path)}: {e}")
            self.script_states[script_path] = 'error'
            main_window.scriptStateChanged.emit(script_path, 'error')

    def check_dependencies_and_run(self, script_path, runner, main_window, stop_at_produces=False, force_run=False):
        """
        Punto de entrada inicial para ejecutar un script, verificando las dependencias
        antes de iniciar el proceso recursivo.
        """
        self.update_states_from_registry()

        script_graph = self.graph.subgraph(nx.ancestors(self.graph, script_path) | {script_path})
        
        missing_dependencies = set()
        for u, v, data in script_graph.edges(data=True):
            if self.script_states[u] not in ['finished', 'partial_finished']:
                missing_dependencies.add(data['var'])
        
        if missing_dependencies:
            for pred_path in self.graph.predecessors(script_path):
                if pred_path in self.script_states and self.script_states[pred_path] == 'idle':
                    self.run_script_with_dependencies(pred_path, runner, main_window, False)
        
        self.run_script_with_dependencies(script_path, runner, main_window, stop_at_produces, force_run)
