# README: Sistema de Ejecución y Dependencias de Scripts con DataFrames en Memoria

## Descripción del Proyecto

Sistema modular de Python para ejecutar scripts que gestionan datos, compartiéndolos en memoria y resolviendo dependencias de forma automática. Permite una visualización clara del flujo.

---

## 1. Objetivo

Este sistema está diseñado para gestionar la ejecución de múltiples scripts de Python que procesan datos, con un enfoque en la eficiencia y la claridad. Permite:

* **Ejecutar** scripts que producen **pandas DataFrames** u otras variables.
* **Compartir datos** entre scripts directamente **en la memoria RAM**, eliminando la necesidad de guardar archivos intermedios en el disco.
* **Resolver dependencias** automáticamente: si un script requiere datos que aún no están disponibles, el sistema ejecuta el script que los produce.
* **Visualizar** las dependencias y el estado de ejecución de forma intuitiva a través de una interfaz gráfica.
* **Extender** el sistema fácilmente con nuevos scripts sin modificar el código central.

---

## 2. Estructura del proyecto

```
📂 proyecto/
│
├── main.py                     # Punto de entrada. Lanza la UI o ejecuta scripts desde la terminal.
├── core/
│   ├── __init__.py
│   ├── memory_store.py         # Gestiona la memoria compartida para los DataFrames.
│   ├── dependency_manager.py   # Define las dependencias entre scripts.
│   ├── script_runner.py        # Orquesta la ejecución de scripts con manejo de dependencias.
│   └── visual_ui.py            # Interfaz gráfica para la gestión del sistema.
│
├── scripts/
│   ├── script_a.py             # Ejemplo: Script que genera 'df_pedidos'.
│   ├── script_b.py             # Ejemplo: Script que consume 'df_pedidos' y produce 'df_clientes'.
│   └── ...                     # Aquí se añadirán los nuevos scripts.
│
└── README.md                   # Este archivo.
```

---

## 3. Cómo funciona

### Memoria Compartida (`core/memory_store.py`)

Es un almacén en memoria (un diccionario) protegido con mecanismos de bloqueo (`locks`) para garantizar un acceso seguro desde múltiples hilos. Los scripts interactúan con él usando dos funciones principales:
* `store_data(nombre, valor)`: Para guardar una variable en la memoria.
* `get_data(nombre)`: Para recuperar una variable.

### Registro de Dependencias (`core/dependency_manager.py`)

Cada script se registra en este módulo, declarando qué variables **produce** y cuáles **consume**. Este registro es la clave para que el sistema entienda el flujo de datos.

### Ejecución Inteligente (`core/script_runner.py`)

Cuando se solicita la ejecución de un script, este módulo verifica si las variables que necesita (`consumes`) ya están en memoria.
* Si la variable **existe**, la usa directamente.
* Si la variable **no existe**, el sistema identifica y ejecuta automáticamente el script que la produce.

### Interfaz Visual (`core/visual_ui.py`)

Esta interfaz muestra el estado actual del sistema: una lista de scripts, sus dependencias y su estado de ejecución (pendiente, ejecutando, listo). Proporciona botones para ejecutar scripts, limpiar la memoria y visualizar las dependencias en un gráfico.

---

## 4. Cómo añadir un nuevo script

Añadir un nuevo script es un proceso sencillo y modular:

1.  **Crea el archivo del script** dentro de la carpeta `scripts/` (ej. `scripts/script_c.py`).
2.  **Define la lógica del script** usando las funciones de `memory_store.py` para obtener datos de entrada y guardar los resultados.
3.  **Registra el script** en `core/dependency_manager.py` con sus dependencias:

    ```python
    # En dependency_manager.py
    register_script(
        name="script_c",
        produces=["df_ventas_finales"],
        consumes=["df_pedidos", "df_clientes"]
    )
    ```

    _Dentro de `script_c.py`, usarías:_

    ```python
    from core.memory_store import get_data, store_data

    # El sistema se encargará de ejecutar los scripts que producen estas variables
    df_pedidos = get_data("df_pedidos")
    df_clientes = get_data("df_clientes")

    # Lógica para crear el nuevo DataFrame
    df_ventas_finales = ...

    # Guardar el resultado en la memoria
    store_data("df_ventas_finales", df_ventas_finales)
    ```

---

## 5. Buenas prácticas

* **Modularidad:** Cada script debe ser una unidad funcional e independiente, comunicándose únicamente a través de la memoria compartida.
* **Nombres de Variables Claros:** Usa nombres de variables descriptivos (`df_pedidos_limpios`, `df_ventas_finales`) para evitar conflictos y mejorar la legibilidad.
* **Documentación:** Incluye un `docstring` en cada script que describa qué hace, qué variables produce y cuáles consume.
* **Evitar Dependencias Externas:** No dependas de rutas de archivos absolutas ni de configuraciones de entorno no documentadas.

---

## 6. Ejecución

Este sistema se puede utilizar de varias maneras:

### Modo visual (UI)

```bash
python main.py --ui
```

Inicia la interfaz gráfica que te permite gestionar el sistema visualmente.

### Modo directo (terminal)

```bash
python main.py --run script_b
```

Ejecuta un script específico y todas sus dependencias automáticamente.

### Limpiar la memoria

```bash
python main.py --clear
```

Borra todos los DataFrames almacenados en la memoria compartida.

---

## 7. Tecnologías recomendadas

* **Backend:** Python 3.10+, **pandas** (para DataFrames).
* **Sincronización:** `threading` o `multiprocessing` para la gestión de la memoria compartida.
* **Interfaz Visual:** **Streamlit** (recomendado por su facilidad), `PyQt5` o `Tkinter`.
* **Visualización de dependencias:** **NetworkX** y **Matplotlib** para generar un gráfico de dependencias.
