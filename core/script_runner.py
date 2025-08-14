import subprocess
import os
import tempfile
import sys
import pickle
import re

class ScriptRunner:
    """
    Clase para ejecutar scripts de Python en un subproceso
    y gestionar sus variables de estado.
    """
    def __init__(self, python_executable="python"):
        """
        Inicializa la clase con la ruta al ejecutable de Python.
        """
        self.python_executable = python_executable

    def run_script(self, script_path, state_data, stop_at_produces=False):
        """
        Ejecuta un script de Python con el estado actual del orquestador.
        Las variables de estado se pasan al script a través de un archivo temporal.
        
        Args:
            script_path (str): Ruta al script de Python a ejecutar.
            state_data (dict): Diccionario con las variables de estado.
            stop_at_produces (bool): Si es True, el script se detiene
                                     después de la primera línea PRODUCE.
        
        Returns:
            tuple: (dict de variables producidas, salida del script, error si existe)
        """
        produces = []
        requires = []
        source_code = ""

        with open(script_path, 'r', encoding='utf-8') as f:
            source_code = f.read()

        # Extraer metadatos de los comentarios
        produces_matches = re.findall(r"#\s*ORCHESTRATOR\.PRODUCE:\s*([A-Za-z0-9_, ]+)", source_code)
        requires_matches = re.findall(r"#\s*ORCHESTRATOR\.REQUIRES:\s*([A-Za-z0-9_, ]+)", source_code)
        
        for match in produces_matches:
            produces.extend([var.strip() for var in match.split(',')])
        for match in requires_matches:
            requires.extend([var.strip() for var in match.split(',')])

        # Crear un archivo temporal para el estado de las variables
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as state_file:
            pickle.dump(state_data, state_file)
            state_file_path = state_file.name

        # Crear un script temporal para la ejecución
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".py", encoding='utf-8') as temp_script:
            
            # 1. Importaciones necesarias
            temp_script.write("import sys\nimport os\nimport pickle\n\n")

            # 2. Cargar el estado desde el archivo temporal
            temp_script.write(f"with open(r'{state_file_path}', 'rb') as f:\n")
            temp_script.write("    loaded_state = pickle.load(f)\n")
            temp_script.write("    for var_name, var_value in loaded_state.items():\n")
            temp_script.write("        globals()[var_name] = var_value\n\n")

            # 3. Marcar las variables iniciales
            temp_script.write("initial_globals = set(globals().keys())\n\n")

            # 4. Inyectar el código del usuario.
            temp_script.write(f"# --- Código del script original '{os.path.basename(script_path)}' ---\n")
            
            # Detectar y procesar la directiva de parada
            lines = source_code.splitlines()
            if stop_at_produces:
                produced_vars = set()
                new_lines = []
                for line in lines:
                    new_lines.append(line)
                    if "# ORCHESTRATOR.PRODUCE" in line:
                        var_name = line.split(":")[-1].strip()
                        produced_vars.add(var_name)
                        new_lines.append(f"if '{var_name}' in globals():\n")
                        new_lines.append(f"    print(f'ORCHESTRATOR_PARTIAL_STOP: {var_name}')\n")
                        new_lines.append("    sys.exit(0)\n")
                
                source_code = "\n".join(new_lines)
            
            temp_script.write(source_code)
            temp_script.write("\n\n")

            # 5. Guardar las variables producidas por el script
            # ¡CORRECCIÓN AQUÍ!
            temp_script.write("produced_vars = {}\n") # Línea 1
            temp_script.write(f"for var_name in {produces}:\n") # Línea 2
            temp_script.write("    if var_name in globals() and var_name not in initial_globals:\n")
            temp_script.write("        produced_vars[var_name] = globals()[var_name]\n\n")

            temp_script.write(f"with open(r'{state_file_path}', 'wb') as f:\n")
            temp_script.write("    pickle.dump(produced_vars, f)\n")

            temp_script_path = temp_script.name

        # Ejecutar el script temporal
        try:
            result = subprocess.run([self.python_executable, temp_script_path],
                                    capture_output=True, text=True, check=False,
                                    encoding='utf-8')
            
            output = result.stdout
            error = result.stderr
            
            # Cargar el resultado desde el archivo temporal
            produced_data = {}
            if not error and os.path.exists(state_file_path):
                with open(state_file_path, 'rb') as f:
                    produced_data = pickle.load(f)

        finally:
            # Limpiar archivos temporales
            if os.path.exists(state_file_path):
                os.remove(state_file_path)
            if os.path.exists(temp_script_path):
                os.remove(temp_script_path)
        
        return produced_data, output, error

