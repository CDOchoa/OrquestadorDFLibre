import sys
import os
import networkx as nx
import pandas as pd
import subprocess
from functools import partial
from pathlib import Path
import re
import json

from PySide6.QtGui import (
    QPainter, QFont, QAction, QIcon, QPainterPath, QPolygonF,
    QSyntaxHighlighter, QTextCharFormat, QColor, QTextDocument,
    QBrush, QPen, QKeySequence, QIntValidator, QTextFormat
)
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QListWidget, QTextEdit, QPushButton,
    QVBoxLayout, QFileDialog, QLabel, QSplitter, QMessageBox,
    QMenu, QInputDialog, QHBoxLayout, QToolBar, QLineEdit,
    QTreeView, QFileSystemModel, QDockWidget, QGraphicsEllipseItem,
    QGraphicsPolygonItem, QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsObject, QDialog,
    QStatusBar, QFormLayout, QComboBox, QTimeEdit, QDialogButtonBox,
    QListWidgetItem, QPlainTextEdit, QAbstractItemView
)
from PySide6.QtCore import (
    Qt, QPointF, Signal, Slot, QDir, QPropertyAnimation,
    QEasingCurve, QParallelAnimationGroup, QTimer, QRectF,
    QObject, QRegularExpression, QTime, QDate, QSize, QRect, QDateTime
)

# Importaciones específicas del proyecto
from shared.registry import discover_scripts
from core.script_runner import ScriptRunner
from core.state_manager import StateManager


# --- Mejoras de UI: Resaltador de Sintaxis ---

class PythonHighlighter(QSyntaxHighlighter):
    """Resaltador de sintaxis para código Python."""
    def __init__(self, parent: QTextDocument):
        super().__init__(parent)
        self._rules = []
        self._formats = {}
        
        self.define_formats()
        self.define_rules()

    def define_formats(self):
        """Define los formatos de texto para palabras clave, comentarios, etc."""
        self._formats["keyword"] = self.create_format(QColor("#005C80"), weight=QFont.Bold)
        self._formats["string"] = self.create_format(QColor("#7d2727"))
        self._formats["comment"] = self.create_format(QColor("#808080"), style=QFont.StyleItalic)
        self._formats["function"] = self.create_format(QColor("#924D28"))
        self._formats["builtin"] = self.create_format(QColor("#205F55"), weight=QFont.Bold)
        self._formats["orchestrator_marker"] = self.create_format(QColor("#006400"), weight=QFont.Bold)

    def define_rules(self):
        """Define las reglas de resaltado con expresiones regulares."""
        keywords = ["def", "class", "return", "if", "else", "elif", "while", "for", "in", "import", "from", "as", "try", "except", "finally", "with"]
        builtins = ["print", "len", "range", "str", "int", "list", "dict", "tuple", "open", "sys", "os", "pickle"]
        
        self._rules.extend([
            (fr"\b{keyword}\b", self._formats["keyword"]) for keyword in keywords
        ])
        self._rules.extend([
            (fr"\b{builtin}\b", self._formats["builtin"]) for builtin in builtins
        ])
        
        self._rules.append((r'".*?"', self._formats["string"]))
        self._rules.append((r"'.*?'", self._formats["string"]))
        self._rules.append((r"#.*", self._formats["comment"]))
        self.function_regex = QRegularExpression(r"\b[A-Za-z0-9_]+(?=\()")
        self._rules.append((r"#\s*ORCHESTRATOR\.(PRODUCE|REQUIRES):.*", self._formats["orchestrator_marker"]))

    def create_format(self, color: QColor, weight=QFont.Normal, style=QFont.StyleNormal):
        """Ayudante para crear un QTextCharFormat."""
        text_format = QTextCharFormat()
        text_format.setForeground(color)
        text_format.setFontWeight(weight)
        text_format.setFontItalic(style == QFont.StyleItalic)
        return text_format

    def highlightBlock(self, text: str):
        """Aplica las reglas de resaltado a un bloque de texto."""
        for pattern, fmt in self._rules:
            expression = QRegularExpression(pattern)
            it = expression.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
        
        # Resaltado de nombres de funciones
        it = self.function_regex.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self._formats["function"])

# --- Editor de Código Avanzado con Números de Línea ---

class LineNumberArea(QWidget):
    """Widget que muestra los números de línea."""
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.code_editor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    """Editor con números de línea y resaltado."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)
        self.setReadOnly(True)
        self.highlightCurrentLine()

    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        return 3 + self.fontMetrics().horizontalAdvance('9') * digits

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(),
                                               self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        h = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#707070"))
                painter.drawText(0, top, self.lineNumberArea.width(), h, Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlightCurrentLine(self):
        extra = []
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor("#eaeaea"))
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        extra.append(sel)
        self.setExtraSelections(extra)


# --- Clases de Visualización de Grafo (NetworkX + QGraphics) ---

class NodeItem(QGraphicsEllipseItem):
    """
    Representa un nodo (script) en el grafo de dependencias con un indicador de estado.
    """
    STATE_COLORS = {
        'idle': QColor("#a3c1da"), # Gris-azul claro
        'running': QColor("yellow"),
        'partial_finished': QColor("#ff8c00"), # Naranja
        'finished': QColor("green"),
        'error': QColor("red")
    }
    
    def __init__(self, x, y, width, height, label, path, parent=None):
        super().__init__(x, y, width, height, parent)
        self.setBrush(QBrush(QColor("#a3c1da")))
        self.setPen(QPen(QColor("#557a95"), 2))
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.label = label
        self.path = path
        self.edges = []
        self.state = 'idle'
        
        self.text = QGraphicsTextItem(label, self)
        self.text.setDefaultTextColor(QColor("#203040"))
        font = QFont("Arial", 10, QFont.Bold)
        self.text.setFont(font)
        
        self.setup_layout(width, height)

    def setup_layout(self, width, height):
        """Centra el texto dentro de la elipse."""
        tw = self.text.boundingRect().width()
        th = self.text.boundingRect().height()
        self.text.setPos(self.rect().x() + (width - tw) / 2, self.rect().y() + (height - th) / 2)
            
    def set_state(self, state):
        """Actualiza el estado visual del nodo."""
        self.state = state
        self.setBrush(QBrush(self.STATE_COLORS.get(state, self.STATE_COLORS['idle'])))
        self.update()

    def itemChange(self, change, value):
        """Mantiene los bordes conectados al nodo cuando se mueve."""
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_position()
        return super().itemChange(change, value)
    
    def mouseDoubleClickEvent(self, event):
        """Muestra detalles del script al hacer doble clic."""
        main_window = self.scene().views()[0].main_window
        main_window.show_script_details(self.path)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """Define un menú contextual para cada nodo (script)."""
        menu = QMenu()
        run_action = QAction("Correr", menu)
        run_partial_action = QAction("Correr y cargar variables", menu)
        view_vars_action = QAction("Ver Variables", menu)
        schedule_action = QAction("Programar Script", menu)

        main_window = self.scene().views()[0].main_window
        run_action.triggered.connect(lambda: main_window.on_run_script_from_node(self.path))
        run_partial_action.triggered.connect(lambda: main_window.on_run_partial_script_from_node(self.path))
        view_vars_action.triggered.connect(lambda: main_window.view_variables(self.path))
        schedule_action.triggered.connect(lambda: main_window.on_schedule_script(self.path))
        
        menu.addAction(run_action)
        
        if self.state == 'partial_finished':
            continue_action = QAction("Continuar carga del script", menu)
            continue_action.triggered.connect(lambda: main_window.on_run_script_from_node(self.path, force_run=True))
            menu.addAction(continue_action)
        else:
            menu.addAction(run_partial_action)
            
        menu.addAction(view_vars_action)
        menu.addAction(schedule_action)
        menu.exec(event.screenPos())

class EdgeItem(QGraphicsLineItem):
    """
    Representa una arista de dependencia entre dos nodos, con una punta de flecha.
    """
    def __init__(self, source_item: NodeItem, dest_item: NodeItem):
        super().__init__()
        self.source_item = source_item
        self.dest_item = dest_item
        
        self.setPen(QPen(QColor("#778899"), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        
        self.arrow = QGraphicsPolygonItem(self)
        self.arrow.setPen(QPen(QColor("#778899"), 1))
        self.arrow.setBrush(QBrush(QColor("#778899")))
        self.arrow.setZValue(2)

        self.update_position()
        self.source_item.edges.append(self)
        self.dest_item.edges.append(self)
        self.setZValue(1)
        
    def update_position(self, source_item=None, dest_item=None):
        """Ajusta la posición de la arista y la flecha para que no se superpongan con los nodos."""
        source_item = source_item or self.source_item
        dest_item = dest_item or self.dest_item

        source_rect = source_item.rect()
        dest_rect = dest_item.rect()

        source_center = source_item.pos() + source_rect.center()
        dest_center = dest_item.pos() + dest_rect.center()
        
        line_vector = dest_center - source_center
        line_length = (line_vector.x()**2 + line_vector.y()**2)**0.5
        
        if line_length > 0:
            unit_vector = line_vector / line_length
            
            source_offset = source_rect.width() / 2
            dest_offset = dest_rect.width() / 2
            
            start_point = source_center + source_offset * unit_vector
            end_point = dest_center - dest_offset * unit_vector
            
            self.setLine(start_point.x(), start_point.y(), end_point.x(), end_point.y())
            
            normal_vector = QPointF(-unit_vector.y(), unit_vector.x())
            arrow_size = 15
            
            arrow_p1 = end_point - arrow_size * unit_vector + arrow_size/2 * normal_vector
            arrow_p2 = end_point - arrow_size * unit_vector - arrow_size/2 * normal_vector
            
            arrow_polygon = QPolygonF([end_point, arrow_p1, arrow_p2])
            self.arrow.setPolygon(arrow_polygon)
        else:
            self.setLine(source_center.x(), source_center.y(), dest_center.x(), dest_center.y())


class GraphView(QGraphicsView):
    """
    Widget principal para mostrar el grafo de dependencias de scripts.
    """
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.nodes = {}
        self.edges = []
        
    def clear(self):
        """Limpia la escena del grafo y sus registros."""
        self.scene.clear()
        self.nodes.clear()
        self.edges.clear()

    def add_node(self, path, label, pos):
        """Agrega un nodo visual al grafo."""
        node = NodeItem(pos.x(), pos.y(), 140, 60, label, path)
        self.scene.addItem(node)
        self.nodes[path] = node
        return node

    def add_edge(self, source_path, dest_path):
        """Agrega una arista de dependencia entre dos nodos."""
        s = self.nodes.get(source_path)
        d = self.nodes.get(dest_path)
        if s and d:
            edge = EdgeItem(s, d)
            self.scene.addItem(edge)
            self.edges.append(edge)

class SchedulerDialog(QDialog):
    """Diálogo para configurar la programación de scripts."""
    def __init__(self, scripts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Programar Script")
        self.scripts = scripts
        self.scheduled_script = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.script_combo = QComboBox()
        self.script_combo.addItems([os.path.basename(s) for s in self.scripts])
        form_layout.addRow("Script:", self.script_combo)

        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems(["Diario", "Semanal", "Cada X horas"])
        form_layout.addRow("Frecuencia:", self.frequency_combo)

        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime.currentTime())
        form_layout.addRow("Hora:", self.time_edit)

        self.days_list = QListWidget()
        self.days_list.setSelectionMode(QListWidget.MultiSelection)
        self.days_list.addItems(["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"])
        form_layout.addRow("Días (Semanal):", self.days_list)
        self.days_list.setVisible(False)

        self.hours_interval_input = QLineEdit()
        self.hours_interval_input.setPlaceholderText("Ej: 4")
        self.hours_interval_input.setValidator(QIntValidator(1, 24))
        form_layout.addRow("Cada (horas):", self.hours_interval_input)
        self.hours_interval_input.setVisible(False)

        self.retry_interval_input = QLineEdit()
        self.retry_interval_input.setPlaceholderText("Ej: 30 (minutos)")
        self.retry_interval_input.setValidator(QIntValidator(1, 1440))
        form_layout.addRow("Reintentar cada (min):", self.retry_interval_input)

        self.frequency_combo.currentIndexChanged.connect(self.update_ui_visibility)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def update_ui_visibility(self, index):
        frequency = self.frequency_combo.currentText()
        self.days_list.setVisible(frequency == "Semanal")
        self.hours_interval_input.setVisible(frequency == "Cada X horas")
        self.time_edit.setVisible(frequency in ["Diario", "Semanal"])


class MainWindow(QMainWindow):
    """
    Clase principal que define la ventana de la aplicación.
    """
    scriptStateChanged = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Orquestador de Scripts - Prototipo")
        self.resize(1200, 800)

        # Directorio inicial de proyectos
        self.default_scripts_dir = str(Path(os.getcwd()) / "scripts")
        self.project_roots = [self.default_scripts_dir]
        
        self.registry = {}
        self.state_manager = StateManager(self.registry)
        self.runner = ScriptRunner()
        self.selected_script_path = None
        self.scheduled_scripts = []
        self.scheduler_file = "scheduled_scripts.json"
        
        self.scriptStateChanged.connect(self.handle_script_state_change)

        self.create_widgets()
        self.create_layouts()
        self.create_menus_and_toolbars()
        self.connect_signals()
        
        self.update_project_list()
        self.refresh_all_scripts()
        
        self.load_scheduled_scripts()
        
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.run_scheduled_scripts)
        self.scheduler_timer.start(60000) # Verifica cada minuto
        
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Listo.")

    def create_widgets(self):
        """Crea y configura todos los widgets de la interfaz."""
        self.graph_view = GraphView(main_window=self)
        self.code_editor = CodeEditor()
        self.code_editor.setPlaceholderText("Selecciona un script para ver y editar su código.")
        self.highlighter = PythonHighlighter(self.code_editor.document())
        
        # Nueva estructura de UI para proyectos y exploración de archivos
        self.project_list_widget = QListWidget()
        self.project_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_list_widget.customContextMenuRequested.connect(self.on_project_list_context_menu)
        
        self.file_tree_view = QTreeView()
        self.file_model = QFileSystemModel()
        self.file_model.setFilter(QDir.NoDotAndDotDot | QDir.AllEntries)
        self.file_tree_view.setModel(self.file_model)
        self.file_tree_view.setColumnHidden(1, True)
        self.file_tree_view.setColumnHidden(2, True)
        self.file_tree_view.setColumnHidden(3, True)
        self.file_tree_view.setHeaderHidden(True)
        self.file_tree_view.setRootIsDecorated(False)
        self.file_tree_view.setSelectionMode(QAbstractItemView.SingleSelection)

        self.variables_list = QListWidget()
        self.variables_list.setMinimumHeight(100)
        
        project_dock_layout = QVBoxLayout()
        project_dock_layout.addWidget(QLabel("<b>Proyectos</b>"))
        project_dock_layout.addWidget(self.project_list_widget)
        project_dock_layout.addWidget(QLabel("<b>Archivos</b>"))
        project_dock_layout.addWidget(self.file_tree_view)
        
        left_dock_widget = QWidget()
        left_dock_widget.setLayout(project_dock_layout)

        self.left_dock = QDockWidget("Proyectos y Variables", self)
        self.left_dock.setWidget(left_dock_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.left_dock)

        # Dock de variables
        variables_dock_widget = QWidget()
        variables_dock_layout = QVBoxLayout(variables_dock_widget)
        variables_dock_layout.addWidget(QLabel("<b>Variables Persistidas</b>"))
        variables_dock_layout.addWidget(self.variables_list)
        
        self.variables_dock = QDockWidget("Variables", self)
        self.variables_dock.setWidget(variables_dock_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.variables_dock)

    def create_layouts(self):
        """Organiza los widgets en la ventana principal."""
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(self.graph_view)
        main_splitter.addWidget(self.code_editor)
        main_splitter.setSizes([int(self.height() * 0.6), int(self.height() * 0.4)])
        self.setCentralWidget(main_splitter)

    def create_menus_and_toolbars(self):
        """Crea los menús y barras de herramientas."""
        toolbar = QToolBar("Orquestador")
        self.addToolBar(toolbar)
        
        refresh_action = QAction(QIcon.fromTheme("view-refresh"), "Recargar Todo", self)
        refresh_action.triggered.connect(self.refresh_all_scripts)
        
        self.run_action = QAction(QIcon.fromTheme("media-playback-start"), "Correr", self)
        self.run_action.triggered.connect(self.on_run_selected)
        
        self.run_partial_action = QAction(QIcon.fromTheme("media-seek-forward"), "Correr y cargar variables", self)
        self.run_partial_action.triggered.connect(self.on_run_partial_selected)
        
        self.reset_state_action = QAction(QIcon.fromTheme("edit-clear"), "Reiniciar Estado", self)
        self.reset_state_action.triggered.connect(self.on_reset_state)
        
        self.add_project_action = QAction(QIcon.fromTheme("list-add"), "Agregar Proyecto", self)
        self.add_project_action.triggered.connect(self.on_add_project)

        self.schedule_action = QAction(QIcon.fromTheme("appointment-new"), "Programar Script", self)
        self.schedule_action.triggered.connect(self.on_schedule_script_from_toolbar)
        
        self.python_path_input = QLineEdit()
        self.python_path_input.setPlaceholderText("Ruta al ejecutable de Python")
        self.python_path_input.setText(self.runner.python_executable)
        self.python_path_input.textChanged.connect(self.on_python_path_changed)
        
        file_menu = self.menuBar().addMenu("Archivo")
        file_menu.addAction(self.add_project_action)
        file_menu.addAction(self.schedule_action)

        toolbar.addAction(self.add_project_action)
        toolbar.addAction(refresh_action)
        toolbar.addSeparator()
        toolbar.addAction(self.run_action)
        toolbar.addAction(self.run_partial_action)
        toolbar.addAction(self.reset_state_action)
        toolbar.addAction(self.schedule_action)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Entorno de Python:"))
        toolbar.addWidget(self.python_path_input)

        view_menu = self.menuBar().addMenu("Ver")
        view_menu.addAction(self.left_dock.toggleViewAction())
        view_menu.addAction(self.variables_dock.toggleViewAction())
        
        self.update_toolbar_state()
        
    def connect_signals(self):
        """Conecta las señales de los widgets con sus slots."""
        self.project_list_widget.currentItemChanged.connect(self.on_project_selected)
        self.file_tree_view.clicked.connect(self.on_file_tree_selection)
        self.variables_list.currentItemChanged.connect(self.on_variable_selection)
        self.graph_view.scene.selectionChanged.connect(self.on_graph_selection)

    def closeEvent(self, event):
        """Maneja el evento de cierre para pedir confirmación."""
        reply = QMessageBox.question(self, 'Confirmar Salida',
                                     "¿Estás seguro de que quieres salir?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def build_dependency_graph(self):
        """Construye el grafo de dependencias de scripts usando NetworkX."""
        G = nx.DiGraph()
        for path, meta in self.registry.items():
            name = os.path.basename(path)
            G.add_node(path, name=name, produces=meta["produces"], requires=meta["requires"])

        var_producers = {}
        for path, meta in self.registry.items():
            for var in meta["produces"]:
                var_producers.setdefault(var, []).append(path)

        for path, meta in self.registry.items():
            consumer_path = path
            for var in meta["requires"]:
                producers = var_producers.get(var, [])
                for p_path in producers:
                    G.add_edge(p_path, consumer_path, var=var)
        return G
    
    def on_add_project(self):
        """
        Permite al usuario agregar una carpeta de proyecto a la lista de proyectos.
        """
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly)
        
        if dialog.exec():
            selected_dir = dialog.selectedFiles()[0]
            if selected_dir not in self.project_roots:
                self.project_roots.append(selected_dir)
                self.update_project_list()
                self.refresh_all_scripts()
                self.statusBar().showMessage(f"Proyecto '{os.path.basename(selected_dir)}' agregado.", 5000)

    @Slot(QPointF)
    def on_project_list_context_menu(self, point):
        """Muestra un menú contextual al hacer clic derecho en la lista de proyectos."""
        item = self.project_list_widget.itemAt(point)
        if not item:
            return

        path = item.data(Qt.UserRole)
        # Prevenir eliminar el directorio de scripts por defecto
        if path == self.default_scripts_dir:
            return
            
        menu = QMenu(self)
        remove_action = QAction("Quitar Proyecto", self)
        remove_action.triggered.connect(lambda: self.on_remove_project(path))
        menu.addAction(remove_action)
        menu.exec(self.project_list_widget.mapToGlobal(point))

    def on_remove_project(self, path):
        """
        Quita un proyecto de la lista y actualiza la interfaz.
        """
        reply = QMessageBox.question(self, "Confirmar Eliminación",
                                     f"¿Estás seguro de que quieres quitar el proyecto '{os.path.basename(path)}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            if path in self.project_roots:
                self.project_roots.remove(path)
                self.update_project_list()
                self.refresh_all_scripts()
                self.statusBar().showMessage(f"Proyecto '{os.path.basename(path)}' quitado.", 5000)

    def update_project_list(self):
        """
        Llena el widget de lista de proyectos con las carpetas actuales.
        """
        self.project_list_widget.clear()
        for root in self.project_roots:
            item = QListWidgetItem(os.path.basename(root))
            item.setData(Qt.UserRole, root)
            self.project_list_widget.addItem(item)
        
        # Selecciona el primer elemento por defecto si existe
        if self.project_list_widget.count() > 0:
            self.project_list_widget.setCurrentRow(0)

    @Slot(QListWidgetItem)
    def on_project_selected(self, current_item: QListWidgetItem):
        """
        Maneja la selección en la lista de proyectos, actualizando el árbol de archivos.
        """
        if current_item:
            project_path = current_item.data(Qt.UserRole)
            self.file_model.setRootPath(project_path)
            self.file_tree_view.setRootIndex(self.file_model.index(project_path))
            self.refresh_all_scripts()
        else:
            self.file_tree_view.setRootIndex(self.file_model.index(""))

    def refresh_all_scripts(self):
        """
        Descubre todos los scripts de todos los proyectos y reconstruye el grafo.
        """
        self.registry = {}
        for project_dir in self.project_roots:
            self.registry.update(discover_scripts(project_dir))

        self.state_manager.registry = self.registry
        self.state_manager.graph = self.build_dependency_graph()
        self.build_graph_view()
        self.update_variables_list()
        self.statusBar().showMessage("Proyectos recargados y vista actualizada.", 5000)

    def on_python_path_changed(self, text):
        """Actualiza la ruta del ejecutable de Python para ScriptRunner."""
        self.runner.python_executable = text

    def on_file_tree_selection(self, index):
        """Slot que se activa al seleccionar un archivo en el árbol de archivos."""
        path = self.file_model.filePath(index)
        if path.endswith(".py"):
            self.selected_script_path = path
            self.show_script_details(path)
            self.highlight_graph_node(path)
        else:
            self.selected_script_path = None
            self.code_editor.clear()
        self.update_toolbar_state()

    def highlight_graph_node(self, path):
        """Resalta un nodo en el grafo al seleccionarlo en el árbol."""
        if path in self.graph_view.nodes:
            node = self.graph_view.nodes[path]
            self.graph_view.scene.clearSelection()
            node.setSelected(True)
            self.graph_view.centerOn(node)

    def update_toolbar_state(self):
        """Habilita/deshabilita los botones de la barra de herramientas."""
        is_script_selected = self.selected_script_path is not None
        self.run_action.setEnabled(is_script_selected)
        self.run_partial_action.setEnabled(is_script_selected)
        self.schedule_action.setEnabled(is_script_selected)

    def on_variable_selection(self, current_item):
        """Slot para manejar la selección de variables en la lista."""
        if current_item:
            var_name = current_item.text().split(' ')[0]
            var_value = self.state_manager.data.get(var_name, "Valor no encontrado.")
            
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Valor de la variable '{var_name}'")
            layout = QVBoxLayout(dialog)
            
            if isinstance(var_value, pd.DataFrame):
                text_widget = QTextEdit()
                text_widget.setReadOnly(True)
                text_widget.setPlainText(str(var_value))
                layout.addWidget(text_widget)
            else:
                label = QLabel(str(var_value))
                layout.addWidget(label)
                
            dialog.exec()

    def on_graph_selection(self):
        """Slot para manejar la selección de nodos en el grafo."""
        selected_items = self.graph_view.scene.selectedItems()
        if selected_items:
            selected_node = selected_items[0]
            if isinstance(selected_node, NodeItem):
                self.selected_script_path = selected_node.path
                self.show_script_details(selected_node.path)
        else:
            self.selected_script_path = None
        self.update_toolbar_state()
        
    def show_script_details(self, script_path):
        """Muestra los metadatos y el código de un script en el editor."""
        metadata = self.registry.get(script_path)
        if metadata:
            header = f"Archivo: {os.path.basename(script_path)}\n"
            header += f"Carpeta de Origen: {os.path.dirname(script_path)}\n\n"
            header += f"--- Docstring ---\n{metadata.get('docstring', 'No docstring.')}\n\n"
            header += f"--- Variables Producidas ---\n{', '.join(metadata.get('produces', []))}\n\n"
            header += f"--- Variables Requeridas ---\n{', '.join(metadata.get('requires', []))}\n\n"
            header += f"--- Código Fuente ---\n"
            
            self.code_editor.setPlainText(header + metadata.get('source_code', 'No code found.'))
        else:
            self.code_editor.clear()

    def build_graph_view(self):
        """
        Visualiza el grafo de dependencias en el widget QGraphicsView.
        """
        self.graph_view.clear()
        self.graph = self.state_manager.graph
        if not self.graph.nodes:
            self.code_editor.setPlainText("No hay scripts en el directorio. Usa 'Agregar Proyecto' para cargar.")
            return

        pos = nx.spring_layout(self.graph, seed=42, k=0.5, iterations=50)
        
        nodes_list = list(self.graph.nodes(data=True))
        if not nodes_list: return

        min_x = min(p[0] for p in pos.values()) if pos else 0
        max_x = max(p[0] for p in pos.values()) if pos else 1
        min_y = min(p[1] for p in pos.values()) if pos else 0
        max_y = max(p[1] for p in pos.values()) if pos else 1
        
        graph_width = max_x - min_x if max_x > min_x else 1
        graph_height = max_y - min_y if max_y > min_y else 1
        
        view_width = self.graph_view.width() - 50
        view_height = self.graph_view.height() - 50
        
        scale_x = view_width / graph_width if graph_width > 0 else 1
        scale_y = view_height / graph_height if graph_height > 0 else 1
        scale = min(scale_x, scale_y) * 0.8
        
        for path, data in nodes_list:
            node_pos = QPointF(
                (pos[path][0] - min_x) * scale,
                (pos[path][1] - min_y) * scale
            )
            self.graph_view.add_node(path, data['name'], node_pos)
        
        for u, v, data in self.graph.edges(data=True):
            self.graph_view.add_edge(u, v)

    def on_run_script_from_node(self, path, force_run=False):
        """Ejecuta un script al hacer clic derecho en el nodo del grafo."""
        self.statusBar().showMessage(f"Iniciando ejecución de {os.path.basename(path)}...", 5000)
        self.state_manager.check_dependencies_and_run(path, self.runner, self, stop_at_produces=False, force_run=force_run)
    
    def on_run_partial_script_from_node(self, path):
        """Ejecuta parcialmente un script al hacer clic derecho en el nodo del grafo."""
        self.statusBar().showMessage(f"Iniciando ejecución parcial de {os.path.basename(path)}...", 5000)
        self.state_manager.check_dependencies_and_run(path, self.runner, self, stop_at_produces=True)

    def on_run_selected(self):
        """Maneja la ejecución del script seleccionado."""
        if self.selected_script_path:
            self.on_run_script_from_node(self.selected_script_path)
        else:
            QMessageBox.warning(self, "No script found", "Selecciona un script válido de la lista.")

    def on_run_partial_selected(self):
        """Maneja la ejecución parcial del script seleccionado."""
        if self.selected_script_path:
            self.on_run_partial_script_from_node(self.selected_script_path)
        else:
            QMessageBox.warning(self, "No script found", "Selecciona un script válido de la lista.")
    
    def on_reset_state(self):
        """Reinicia el estado de todos los scripts y variables."""
        self.state_manager.reset_state()
        for path, node in self.graph_view.nodes.items():
            node.set_state('idle')
        self.update_variables_list()
        self.statusBar().showMessage("Estado reiniciado.", 5000)
        QMessageBox.information(self, "Estado Reiniciado", "El estado de todos los scripts y variables ha sido reiniciado.")

    @Slot(str, str)
    def handle_script_state_change(self, script_path: str, state: str):
        """Slot para actualizar el estado visual de un nodo del grafo."""
        node = self.graph_view.nodes.get(script_path)
        if node:
            node.set_state(state)
        self.update_variables_list()
        self.statusBar().showMessage(f"Estado de {os.path.basename(script_path)}: {state}", 5000)

    def update_variables_list(self):
        """Actualiza la lista de variables persistidas en la interfaz."""
        self.variables_list.clear()
        if not self.state_manager.data:
            self.variables_list.addItem("No hay variables en memoria.")
            return

        for var_name, value in self.state_manager.data.items():
            source_script = self.state_manager.get_source_script(var_name)
            item_text = f"{var_name} (de {os.path.basename(source_script)})"
            self.variables_list.addItem(item_text)

    def view_variables(self, path):
        """Muestra un diálogo con las variables producidas y requeridas."""
        meta = self.registry.get(path)
        if not meta:
            QMessageBox.warning(self, "No encontrado", "No se encontró información del script.")
            return
        
        vars_produces = meta.get("produces", [])
        vars_requires = meta.get("requires", [])
        
        vars_text = (
            f"Variables producidas:\n- {', '.join(vars_produces) if vars_produces else 'Ninguna'}\n\n"
            f"Variables requeridas:\n- {', '.join(vars_requires) if vars_requires else 'Ninguna'}"
        )
        QMessageBox.information(self, "Variables del Script", vars_text)

    def on_schedule_script_from_toolbar(self):
        """Inicia el diálogo de programación desde la barra de herramientas."""
        if not self.selected_script_path:
            QMessageBox.warning(self, "No script found", "Selecciona un script para programar.")
            return
        self.on_schedule_script(self.selected_script_path)

    def on_schedule_script(self, script_path):
        """Maneja la programación de scripts."""
        dialog = SchedulerDialog(list(self.registry.keys()), self)
        
        dialog.script_combo.setCurrentText(os.path.basename(script_path))

        if dialog.exec():
            frequency = dialog.frequency_combo.currentText()
            time_str = dialog.time_edit.time().toString("hh:mm")
            
            schedule_config = {
                "script_path": script_path,
                "frequency": frequency,
                "time": time_str,
                "last_run": None
            }

            if frequency == "Semanal":
                selected_days = [dialog.days_list.item(i).text() for i in range(dialog.days_list.count()) if dialog.days_list.item(i).isSelected()]
                schedule_config["days"] = selected_days
            
            elif frequency == "Cada X horas":
                hours = dialog.hours_interval_input.text()
                schedule_config["hours_interval"] = int(hours)
            
            self.scheduled_scripts.append(schedule_config)
            self.save_scheduled_scripts()
            self.statusBar().showMessage(f"Script '{os.path.basename(script_path)}' programado con éxito.", 5000)

    def save_scheduled_scripts(self):
        """Guarda la lista de scripts programados en un archivo JSON."""
        with open(self.scheduler_file, "w") as f:
            json.dump(self.scheduled_scripts, f)

    def load_scheduled_scripts(self):
        """Carga los scripts programados desde un archivo JSON."""
        if os.path.exists(self.scheduler_file):
            with open(self.scheduler_file, "r") as f:
                try:
                    self.scheduled_scripts = json.load(f)
                except json.JSONDecodeError:
                    self.scheduled_scripts = []

    def run_scheduled_scripts(self):
        """Verifica y ejecuta los scripts programados."""
        now = QTime.currentTime()
        now_str = now.toString("hh:mm")
        current_day = QDate.currentDate().dayOfWeek() # 1=Lunes, 7=Domingo
        days_of_week = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
        for script_config in self.scheduled_scripts:
            script_path = script_config.get("script_path")
            frequency = script_config.get("frequency")
            
            if frequency == "Diario" and script_config.get("time") == now_str:
                self.state_manager.check_dependencies_and_run(script_path, self.runner, self)
                script_config["last_run"] = QDateTime.currentDateTime().toString(Qt.ISODate)

            elif frequency == "Semanal" and script_config.get("time") == now_str:
                if days_of_week[current_day - 1] in script_config.get("days", []):
                    self.state_manager.check_dependencies_and_run(script_path, self.runner, self)
                    script_config["last_run"] = QDateTime.currentDateTime().toString(Qt.ISODate)
            
            elif frequency == "Cada X horas":
                hours_interval = script_config.get("hours_interval")
                last_run_str = script_config.get("last_run")
                
                if not last_run_str:
                    self.state_manager.check_dependencies_and_run(script_path, self.runner, self)
                    script_config["last_run"] = QDateTime.currentDateTime().toString(Qt.ISODate)
                else:
                    last_run_time = QDateTime.fromString(last_run_str, Qt.ISODate)
                    if last_run_time.addSecs(hours_interval * 3600) <= QDateTime.currentDateTime():
                        self.state_manager.check_dependencies_and_run(script_path, self.runner, self)
                        script_config["last_run"] = QDateTime.currentDateTime().toString(Qt.ISODate)

        self.save_scheduled_scripts()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())