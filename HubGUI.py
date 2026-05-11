# PyQtHub.py
import sys
import signal
import importlib
import inspect

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QMessageBox, QMainWindow
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


# --- dynamic child loading ----------------------------------------------------
def find_qmainwindow_class(module):
    """Return the first QMainWindow subclass defined in the given module."""
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, QMainWindow) and obj.__module__ == module.__name__:
            return obj
    return None


def load_window_from_module(module_name):
    mod = importlib.import_module(module_name)
    cls = find_qmainwindow_class(mod)
    if not cls:
        raise RuntimeError(f"No QMainWindow subclass found in '{module_name}'.")
    return cls()


# --- main hub -----------------------------------------------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Main Menu")
        self.resize(550, 160) # Increased width slightly to accommodate the 5th button
        self._child = None

        layout = QVBoxLayout(self)

        # Font selector (applies app-wide)
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font Size:"))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(8, 32)
        self.font_slider.setValue(12)
        self.font_slider.setTickInterval(1)
        self.font_value = QLabel(str(self.font_slider.value()))
        self.font_slider.valueChanged.connect(self._on_font_change)
        font_row.addWidget(self.font_slider, 1)
        font_row.addWidget(self.font_value)
        layout.addLayout(font_row)

        # Launch buttons
        btn_row = QHBoxLayout()
        for label, module in [("Open Article Scraper", "ArticleScraperGUI"),
                              ("Open Auto File Search Chatbot", "ChatbotAutoGUI"),
                              ("Open Article Embedder", "EmbedderGUI"),
                              ("Open Embed File Search Chatbot", "EmbedChatGUI"),
                              ("Open Manual PDF Converter", "ManualPDFConversion")]: # Added new module here
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, m=module: self.open_child(m))
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        # Initialize app-wide font
        self._apply_app_font(self.font_slider.value())

    # --- font handling (global) ---
    def _on_font_change(self, size: int):
        self.font_value.setText(str(size))
        self._apply_app_font(size)

    def _apply_app_font(self, size: int):
        f = QFont()
        f.setPointSize(size)
        # Set on QApplication so all existing & future windows inherit it.
        QApplication.instance().setFont(f)
        # Also set on the hub explicitly so its slider/labels update immediately.
        self.setFont(f)

    # --- child lifecycle ---
    def open_child(self, module_name: str):
        app = QApplication.instance()
        try:
            child = load_window_from_module(module_name)
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", str(e))
            return

        # Ensure closing the child actually destroys it, so 'destroyed' fires.
        child.setAttribute(Qt.WA_DeleteOnClose, True)

        # While the child is open, closing it should NOT quit the app
        # (the hub will be hidden).
        app.setQuitOnLastWindowClosed(False)

        # When the child is destroyed (closed), reshow hub & restore default behavior.
        child.destroyed.connect(self._on_child_closed)

        child.show()
        child.raise_()
        child.activateWindow()
        self._child = child
        self.hide()

    def _on_child_closed(self, *_):
        self._child = None
        QApplication.instance().setQuitOnLastWindowClosed(True)
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        # If user closes the hub itself, exit cleanly.
        if self._child is not None:
            try:
                self._child.close()
            except Exception:
                pass
            self._child = None
        super().closeEvent(e)


# --- entry point --------------------------------------------------------------
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)

    # Default: quit when the last (visible) window closes.
    app.setQuitOnLastWindowClosed(True)

    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
