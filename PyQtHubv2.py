# hub_gui.py
import sys
import signal
import importlib
import inspect

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QMessageBox, QMainWindow
)
from PyQt5.QtCore import Qt, QEvent, QTimer
from PyQt5.QtGui import QFont


def find_qmainwindow_class(module):
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


def apply_font_size_to_child(child, size):
    try:
        if hasattr(child, "font_slider"):
            try:
                child.font_slider.blockSignals(True)
                child.font_slider.setValue(size)
            finally:
                child.font_slider.blockSignals(False)
            if hasattr(child, "change_font_size") and callable(child.change_font_size):
                child.change_font_size(size)
            return
        if hasattr(child, "change_font_size") and callable(child.change_font_size):
            child.change_font_size(size)
            return
    except Exception:
        pass
    f = QFont()
    f.setPointSize(size)
    child.setFont(f)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Main Menu")
        self.resize(420, 180)
        self._child = None

        layout = QVBoxLayout()

        # Font selector
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font Size:"))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(8, 32)
        self.font_slider.setValue(12)
        self.font_slider.setTickInterval(1)
        self.font_value = QLabel("12")
        self.font_slider.valueChanged.connect(self._on_font_change)
        font_row.addWidget(self.font_slider)
        font_row.addWidget(self.font_value)
        layout.addLayout(font_row)

        # Buttons
        btn_row = QHBoxLayout()
        b1 = QPushButton("Open PyQt5v7")
        b2 = QPushButton("Open PyQtCLIv8")
        b1.clicked.connect(lambda: self.open_child("PyQt5v7"))
        b2.clicked.connect(lambda: self.open_child("PyQtCLIv8"))
        btn_row.addWidget(b1)
        btn_row.addWidget(b2)
        layout.addLayout(btn_row)

        self.setLayout(layout)
        self._apply_font_to_self(self.font_slider.value())

    # --- font helpers ---
    def _on_font_change(self, value: int):
        self.font_value.setText(str(value))
        self._apply_font_to_self(value)

    def _apply_font_to_self(self, size: int):
        f = QFont()
        f.setPointSize(size)
        self.setFont(f)

    # --- child lifecycle ---
    def open_child(self, module_name: str):
        app = QApplication.instance()
        try:
            child = load_window_from_module(module_name)
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", str(e))
            return

        apply_font_size_to_child(child, self.font_slider.value())

        # 1) While the child is open, DO NOT quit when last window closes.
        app.setQuitOnLastWindowClosed(False)

        # 2) Watch for child's Close; when it closes, reshow hub and restore default behavior.
        child.installEventFilter(self)

        child.show()
        child.raise_()
        child.activateWindow()
        self._child = child
        self.hide()

    def eventFilter(self, obj, event):
        if obj is self._child and event.type() == QEvent.Close:
            QTimer.singleShot(0, self._on_child_closed)
        return super().eventFilter(obj, event)

    def _on_child_closed(self):
        self._child = None
        # Back at the hub → restore default so closing the hub exits the app.
        QApplication.instance().setQuitOnLastWindowClosed(True)
        self.show()
        self.raise_()
        self.activateWindow()

    # If the user closes the hub while it's visible, exit cleanly.
    # (With quitOnLastWindowClosed=True, this would already exit, but this
    # ensures termination even if someone toggled it elsewhere.)
    def closeEvent(self, e):
        # If a child is still around for some reason, close it too.
        if self._child is not None:
            try:
                self._child.close()
            except Exception:
                pass
            self._child = None
        super().closeEvent(e)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)

    # Default: quit when the last window (the hub) closes.
    app.setQuitOnLastWindowClosed(True)

    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
