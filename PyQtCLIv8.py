# Fixed tool use (was broken since v5 and didn't realize it)
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QLineEdit, QPushButton, QSpinBox, QCheckBox,
    QFileDialog, QComboBox, QVBoxLayout, QHBoxLayout,
    QTextEdit, QSlider
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIntValidator, QFont

# Import the existing functions from your CLI module
from cli import run_result_gatherer, run_file_gatherer, run_text_converter

class EmittingStream:
    def __init__(self, signal):
        self.signal = signal
        self._buf = ""

    def write(self, text):
        if not text:
            return
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self.signal.emit(line)

    def flush(self):
        if self._buf.strip():
            self.signal.emit(self._buf.rstrip("\n"))
        self._buf = ""

class Worker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, cmd, query, directory, total, year_start, year_end, meta, use_range):
        super().__init__()
        self.cmd = cmd
        self.query = query
        self.directory = directory
        self.total = total
        self.year_start = year_start if use_range else None
        self.year_end = year_end if use_range else None
        self.meta = meta

    # def run(self):
    #     import builtins
    #     original_stdout = sys.stdout
    #     original_stderr = sys.stderr
    #     original_print = builtins.print
    #     stream = EmittingStream(self.progress)
    #     sys.stdout = stream
    #     sys.stderr = stream
    #     builtins.print = lambda *a, **k: original_print(*a, flush=True, **k)
    #     try:
    #         if self.cmd == 'all':
    #             results = run_result_gatherer(
    #                 self.query, self.directory,
    #                 self.total, self.year_start, self.year_end
    #             )
    #             self.progress.emit(f"Gathered {len(results)} results.")
    #
    #             run_file_gatherer(
    #                 self.query, self.directory,
    #                 self.year_start, self.year_end, self.meta
    #             )
    #             self.progress.emit("Files gathered.")
    #
    #             run_text_converter(self.directory)
    #             self.progress.emit("Text conversion completed.")
    #
    #         elif self.cmd == 'results':
    #             results = run_result_gatherer(
    #                 self.query, self.directory,
    #                 self.total, self.year_start, self.year_end
    #             )
    #             self.progress.emit(f"Gathered {len(results)} results.")
    #
    #         elif self.cmd == 'files':
    #             run_file_gatherer(
    #                 self.query, self.directory,
    #                 self.year_start, self.year_end, self.meta
    #             )
    #             self.progress.emit("Files gathered.")
    #
    #         elif self.cmd == 'convert':
    #             run_text_converter(self.directory)
    #             self.progress.emit("Text conversion completed.")
    #
    #         self.finished.emit("Completed successfully.")
    #
    #     except Exception as e:
    #         self.error.emit(str(e))
    #
    #     finally:
    #         import builtins
    #         sys.stdout = original_stdout
    #         sys.stderr = original_stderr
    #         builtins.print = original_print

    def run(self):
        # Redirect stdout to GUI in real-time
        original_stdout = sys.stdout
        sys.stdout = EmittingStream(self.progress)
        try:
            if self.cmd == 'all':
                results = run_result_gatherer(
                    self.query, self.directory,
                    self.total, self.year_start, self.year_end
                )
                self.progress.emit(f"Gathered {len(results)} results.")

                run_file_gatherer(
                    self.query, self.directory,
                    self.year_start, self.year_end, self.meta
                )
                self.progress.emit("Files gathered.")

                run_text_converter(self.directory)
                self.progress.emit("Text conversion completed.")

            elif self.cmd == 'results':
                results = run_result_gatherer(
                    self.query, self.directory,
                    self.total, self.year_start, self.year_end
                )
                self.progress.emit(f"Gathered {len(results)} results.")

            elif self.cmd == 'files':
                run_file_gatherer(
                    self.query, self.directory,
                    self.year_start, self.year_end, self.meta
                )
                self.progress.emit("Files gathered.")

            elif self.cmd == 'convert':
                run_text_converter(self.directory)
                self.progress.emit("Text conversion completed.")

            self.finished.emit("Completed successfully.")

        except Exception as e:
            self.error.emit(str(e))

        finally:
            # Restore original stdout
            sys.stdout = original_stdout

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scholar Tool GUI")
        self.worker = None
        self.current_font_size = 12
        self.init_ui()

    def init_ui(self):
        font = QFont()
        font.setPointSize(self.current_font_size)
        self.setFont(font)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout()

        # Font size slider with display label
        font_layout = QHBoxLayout()
        font_label = QLabel("Font Size:")
        self.font_size_display = QLabel(str(self.current_font_size))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(8, 24)
        self.font_slider.setValue(self.current_font_size)
        self.font_slider.valueChanged.connect(self.change_font_size)
        font_layout.addWidget(font_label)
        font_layout.addWidget(self.font_slider)
        font_layout.addWidget(self.font_size_display)
        layout.addLayout(font_layout)

        cmd_layout = QHBoxLayout()
        cmd_label = QLabel("Scraping Command:")
        self.cmd_combo = QComboBox()
        self.cmd_combo.addItems(["all", "results", "files", "convert"])
        self.cmd_combo.currentTextChanged.connect(self.update_fields)
        cmd_layout.addWidget(cmd_label)
        cmd_layout.addWidget(self.cmd_combo)
        layout.addLayout(cmd_layout)

        self.query_label = QLabel("Search Query:")
        self.query_edit = QLineEdit()
        layout.addWidget(self.query_label)
        layout.addWidget(self.query_edit)

        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("Directory to save to:")
        self.dir_edit = QLineEdit()
        self.dir_btn = QPushButton("Browse")
        self.dir_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.dir_edit)
        dir_layout.addWidget(self.dir_btn)
        layout.addLayout(dir_layout)

        tot_layout = QHBoxLayout()
        self.tot_label = QLabel("Total Results:")
        self.tot_spin = QSpinBox()
        self.tot_spin.setRange(1, 10000)
        self.tot_spin.setValue(100)
        tot_layout.addWidget(self.tot_label)
        tot_layout.addWidget(self.tot_spin)
        layout.addLayout(tot_layout)

        self.range_chk = QCheckBox("Use date range")
        self.range_chk.setChecked(False)
        self.range_chk.stateChanged.connect(self.update_range_fields)
        layout.addWidget(self.range_chk)

        year_layout = QHBoxLayout()
        self.start_label = QLabel("Year Start:")
        self.start_edit = QLineEdit()
        self.start_edit.setPlaceholderText("1900-2100 or blank")
        self.start_edit.setValidator(QIntValidator(1900, 2100))
        self.end_label = QLabel("Year End:")
        self.end_edit = QLineEdit()
        self.end_edit.setPlaceholderText("1900-2100 or blank")
        self.end_edit.setValidator(QIntValidator(1900, 2100))
        year_layout.addWidget(self.start_label)
        year_layout.addWidget(self.start_edit)
        year_layout.addWidget(self.end_label)
        year_layout.addWidget(self.end_edit)
        layout.addLayout(year_layout)

        self.meta_chk = QCheckBox("Meta can be missing")
        layout.addWidget(self.meta_chk)

        self.run_btn = QPushButton("Run")
        layout.addWidget(self.run_btn)
        self.run_btn.clicked.connect(self.run_command)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        central.setLayout(layout)
        self.update_fields(self.cmd_combo.currentText())
        self.update_range_fields(self.range_chk.checkState())

    def change_font_size(self, value):
        self.current_font_size = value
        self.font_size_display.setText(str(value))
        font = QFont()
        font.setPointSize(self.current_font_size)
        self.setFont(font)
        self.output.setStyleSheet(f"font-size: {self.current_font_size}pt;")

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            self.dir_edit.setText(dir_path)

    def update_fields(self, cmd):
        is_all = cmd == "all"
        is_res = cmd == "results"
        is_files = cmd == "files"
        is_conv = cmd == "convert"

        self.query_label.setVisible(is_all or is_res or is_files)
        self.query_edit.setVisible(is_all or is_res or is_files)
        self.tot_label.setVisible(is_all or is_res)
        self.tot_spin.setVisible(is_all or is_res)

        hide_dates = is_conv
        self.range_chk.setVisible(not hide_dates)
        self.start_label.setVisible(not hide_dates)
        self.start_edit.setVisible(not hide_dates)
        self.end_label.setVisible(not hide_dates)
        self.end_edit.setVisible(not hide_dates)

        self.meta_chk.setVisible(is_all or is_files)

    def update_range_fields(self, state):
        enabled = (state == Qt.Checked)
        self.start_label.setEnabled(enabled)
        self.start_edit.setEnabled(enabled)
        self.end_label.setEnabled(enabled)
        self.end_edit.setEnabled(enabled)

    def run_command(self):
        if self.worker and self.worker.isRunning():
            return

        cmd = self.cmd_combo.currentText()
        query = self.query_edit.text().strip()
        directory = self.dir_edit.text().strip()
        total = self.tot_spin.value()
        use_range = self.range_chk.isChecked()
        ys = self.start_edit.text().strip() if use_range else ''
        ye = self.end_edit.text().strip() if use_range else ''
        year_start = int(ys) if ys else None
        year_end = int(ye) if ye else None
        meta = self.meta_chk.isChecked()

        self.run_btn.setEnabled(False)
        self.output.clear()

        self.worker = Worker(cmd, query, directory, total, year_start, year_end, meta, use_range)
        self.worker.progress.connect(self.output.append)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_finished(self, message):
        self.output.append(f"<span style='color:green;'>{message}</span>")
        self.run_btn.setEnabled(True)

    def on_error(self, errmsg):
        self.output.append(f"<span style='color:red;'>Error: {errmsg}</span>")
        self.run_btn.setEnabled(True)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
