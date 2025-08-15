# OrquestadorDFLibre: Un Orquestador de Scripts de Python No Intrusivo

---

## 🚀 Filosofía del Proyecto

La filosofía principal de **OrquestadorDFLibre** es la **no intrusión**. A diferencia de otros orquestadores que te obligan a reestructurar tus scripts para que se adapten a una plantilla o clase específica, este proyecto se adapta a tu flujo de trabajo actual.

El concepto es simple: tú escribes tu código, y la herramienta gestiona las dependencias. Esto se logra mediante un sistema de metadatos sencillo: comentarios de una sola línea. Al añadir `# ORCHESTRATOR.REQUIRES` y `# ORCHESTRATOR.PRODUCE` en cualquier parte de tu script, la herramienta puede identificar las variables de entrada y salida para construir un **grafo de dependencias**. No necesitas modificar la lógica o la estructura interna de tu código.

Este enfoque ofrece varias ventajas:

* Puedes integrar un script de Python que ya tienes con solo un par de comentarios.
* Tus scripts siguen siendo legibles y se pueden ejecutar de forma independiente.
* Se reduce significativamente la curva de aprendizaje y el tiempo de integración.

---

## 🧠 Cómo Funciona

El orquestador opera en tres fases principales:

### 1. Registro y Análisis de Scripts

La herramienta escanea el directorio de scripts para encontrar archivos `.py`. En cada archivo, busca los comentarios de metadatos para construir una "receta" del script, identificando sus requisitos y sus productos. Con esta información, crea un **Grafo Dirigido Acíclico (DAG)** que representa el flujo de dependencias entre los scripts. Por ejemplo, si `script_b.py` requiere `df_initial` y `script_a.py` produce esa variable, el orquestador sabe que `script_a` debe ejecutarse antes que `script_b`. 

### 2. Gestión del Estado y Variables

El orquestador mantiene un estado persistente de las variables que cada script produce, guardándolo en un archivo llamado **`state.pkl`**. Antes de ejecutar un script, el orquestador carga las variables necesarias desde este archivo y las inyecta en el entorno de ejecución del script. Una vez que el script finaliza, captura las variables que ha producido y las guarda en el archivo de estado para que otros scripts puedan usarlas.

### 3. Ejecución Inteligente

Cuando solicitas ejecutar un script, el orquestador primero revisa el DAG para identificar todas sus dependencias. Si una dependencia ya se ha ejecutado y su variable está disponible, la salta para ahorrar tiempo. Si faltan variables, detiene la ejecución y notifica el error. Esta "ejecución inteligente" garantiza que el flujo de trabajo sea eficiente y reproducible, asegurando que los datos estén siempre disponibles para el script correcto en el momento adecuado.

---

## 📦 Requisitos del Sistema

Para que el proyecto funcione correctamente, necesitas las siguientes dependencias de Python, que puedes instalar fácilmente con `pip` o configurar en tu entorno de Conda.

**Dependencias principales:**

* **pandas:** Indispensable para el manejo y análisis de datos.
* **networkx:** Utilizado para construir y gestionar el grafo de dependencias.
* **python-dotenv (opcional):** Recomendado para gestionar variables de entorno de forma segura.
* **pyqt5 (si usas la interfaz de usuario):** Para la interfaz gráfica que acompaña al orquestador.

### El archivo `requirements.txt`

Para garantizar que tu entorno de Python sea idéntico al del desarrollo, puedes usar el archivo `requirements.txt`.

**Cómo usarlo:**

1.  Crea un archivo llamado `requirements.txt` en la raíz de tu proyecto.
2.  Copia y pega el siguiente contenido:

```
pandas
networkx
python-dotenv
pyqt5
```

3.  Desde tu terminal, asegúrate de estar en el mismo directorio que el archivo y ejecuta el siguiente comando:

```bash
pip install -r requirements.txt
```

---

## 📂 Estructura del Proyecto

Para entender completamente el proyecto, es crucial conocer la función de cada archivo y directorio. Esta estructura está diseñada para mantener una clara separación de responsabilidades, haciendo el proyecto escalable y fácil de mantener.

```
/OrquestadorDFLibre
│
├── main.py                    # El punto de entrada principal que inicializa la aplicación.
│
├── state.pkl                  # Archivo de estado persistente que almacena variables y DataFrames.
│
├── requirements.txt           # Lista de dependencias del proyecto.
│
├── /core/                     # Directorio con la lógica central del orquestador.
│   │
│   ├── state_manager.py       # El "cerebro" del orquestador; gestiona el estado, el grafo y la ejecución.
│   │
│   ├── registry.py            # Escanea scripts y extrae metadatos para construir la "receta" de cada uno.
│   │
│   └── runner.py              # Contiene la lógica para ejecutar scripts y manejar la inyección/captura de variables.
│
├── /scripts/                  # El corazón del proyecto; aquí se guardan tus scripts.
│   │
│   ├── script_a.py            # Un script de ejemplo.
│   │
│   └── script_b.py            # Otro script de ejemplo que podría depender de `script_a.py`.
│
└── /ui/                       # Directorio para los archivos de la interfaz de usuario.
    │
    ├── main_window.py         # Define la ventana principal y los elementos de la UI.
    │
    └── ui_logic.py            # Lógica para actualizar el estado visual de la UI.
```