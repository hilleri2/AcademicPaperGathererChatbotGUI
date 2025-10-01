# hub_gui.py
import sys
import importlib
import inspect
from typing import Optional, Type

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QGroupBox, QMessageBox
)

# --- Utility: find a QMainWindow subclass in a module ---
def find_qmainwindow_class(mod) -> Optional[Type[QMainWindow]]:
    """
    Returns the first class in `mod` that is a subclass of QMainWindow.
    """
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, QMainWindow) and obj.__module__ == mod.__name__:
            return obj
    return None

# --- Hub Window ---
class HubWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hub – Launch GUIs")
        self.setGeometry(200, 200, 420, 220)

        # Default font size
        self.current_font_size = 12
        base_font = QFont()
        base_font.setPointSize(self.current_font_size)
        self.setFont(base_font)

        # Track currently opened child window
        self.child_window: Optional[QMainWindow] = None

        # Central layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Font group
        font_group = QGroupBox("Font")
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font Size:"))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(8, 32)
        self.font_slider.setTickInterval(1)
        self.font_slider.setValue(self.current_font_size)
        self.font_slider.valueChanged.connect(self.on_font_changed)
        font_layout.addWidget(self.font_slider)
        self.font_value = QLabel(str(self.current_font_size))
        font_layout.addWidget(self.font_value)
        font_group.setLayout(font_layout)
        main_layout.addWidget(font_group)

        # Launch buttons
        btn_row = QHBoxLayout()
        self.btn_pyqt5 = QPushButton("Open PyQt5v7")
        self.btn_pyqt5.clicked.connect(lambda: self.launch_module("PyQt5v7"))
        btn_row.addWidget(self.btn_pyqt5)

        self.btn_cli = QPushButton("Open PyQtCLIv8")
        self.btn_cli.clicked.connect(lambda: self.launch_module("PyQtCLIv8"))
        btn_row.addWidget(self.btn_cli)

        main_layout.addLayout(btn_row)

        # Info label
        info = QLabel("Tip: Close a child window and this Hub will pop back up.")
        info.setWordWrap(True)
        main_layout.addWidget(info)

    # -- Handlers --
    def on_font_changed(self, value: int):
        self.current_font_size = value
        self.font_value.setText(str(value))
        f = QFont()
        f.setPointSize(value)
        # Update hub font immediately
        self.setFont(f)

    def launch_module(self, module_name: str):
        """
        Import the module, find its QMainWindow subclass, instantiate it,
        apply font size, wire up close behavior, and show it.
        """
        try:
            mod = importlib.import_module(module_name)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Could not import module '{module_name}'.\n\n{e}"
            )
            return

        cls = find_qmainwindow_class(mod)
        if cls is None:
            QMessageBox.critical(
                self,
                "Launch Error",
                f"No QMainWindow subclass found in '{module_name}'.\n"
                f"Make sure the file defines a class that subclasses QMainWindow."
            )
            return

        try:
            child = cls()  # Create the child window
        except Exception as e:
            QMessageBox.critical(
                self,
                "Init Error",
                f"Failed to instantiate window from '{module_name}'.\n\n{e}"
            )
            return

        self.apply_font_to_child(child, self.current_font_size)

        # When the child window is destroyed/closed, bring back the hub
        child.destroyed.connect(self.on_child_closed)

        # Hide hub while child is open
        self.hide()
        self.child_window = child
        child.show()
        child.raise_()
        child.activateWindow()

    def on_child_closed(self, *args, **kwargs):
        self.child_window = None
        self.show()
        self.raise_()
        self.activateWindow()

    # -- Font transfer logic --
    def apply_font_to_child(self, child: QMainWindow, size: int):
        """
        Tries to propagate the chosen font size into the child window.
        Priority:
          1) If child has a 'font_slider', set it (this tends to trigger the child's own UI refresh).
          2) Else if child has 'change_font_size(int)', call it.
          3) Else fall back to child.setFont(QFont(size)).
        """
        try:
            # Case 1: a slider like in PyQt5v7.py
            if hasattr(child, "font_slider"):
                # Block signals briefly to avoid duplicate UI work; then set & unblock so their handler runs once.
                child.font_slider.blockSignals(True)
                child.font_slider.setValue(size)
                child.font_slider.blockSignals(False)
                # Manually invoke the handler if it exists (some sliders only update on signal)
                if hasattr(child, "change_font_size") and callable(child.change_font_size):
                    child.change_font_size(size)
                return

            # Case 2: explicit method
            if hasattr(child, "change_font_size") and callable(child.change_font_size):
                child.change_font_size(size)
                return

            # Case 3: generic app font
            f = QFont()
            f.setPointSize(size)
            child.setFont(f)
        except Exception:
            # Don't hard fail if the child doesn't support these; last resort setFont again
            f = QFont()
            f.setPointSize(size)
            child.setFont(f)

def main():
    app = QApplication(sys.argv)
    hub = HubWindow()
    hub.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
