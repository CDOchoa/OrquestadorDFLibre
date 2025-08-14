import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

# Lista global para mantener las referencias de las ventanas
# Esto es crucial para que el recolector de basura no las cierre.
open_windows = []

def main():
    """
    Función principal de la aplicación.
    """
    app = QApplication(sys.argv)
    
    # Crea la primera ventana al iniciar la aplicación.
    main_window = MainWindow()
    open_windows.append(main_window)
    main_window.show()

    # Si una ventana se cierra, la eliminamos de la lista global
    # para que la aplicación pueda gestionarla correctamente.
    def on_window_closed(window):
        if window in open_windows:
            open_windows.remove(window)
            if not open_windows: # Cierra la app si no hay más ventanas
                app.quit()

    main_window.destroyed.connect(lambda: on_window_closed(main_window))

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
