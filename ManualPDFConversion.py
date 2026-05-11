# ManualPDFConversion.py
import sys
import os
from pathlib import Path
import pymupdf

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QSlider, QGroupBox,
    QFileDialog, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt5.QtGui import QFont


# --------------------- Worker for background PDF processing --------------------- #

class ConversionWorker(QObject):
    finished = pyqtSignal(str)  # final status message
    error = pyqtSignal(str)  # error message
    progress = pyqtSignal(str)  # progress updates

    def __init__(self, input_dir: str, output_dir: str):
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            # Validation
            if not self.input_dir or not os.path.isdir(self.input_dir):
                self.error.emit(f"Error: Input directory not found: {self.input_dir}")
                return
            if not self.output_dir or not os.path.isdir(self.output_dir):
                self.error.emit(f"Error: Output directory not found: {self.output_dir}")
                return

            self.progress.emit("Scanning input directory for .pdf files...")
            path_list = list(Path(self.input_dir).glob("**/*.pdf"))

            if not path_list:
                self.error.emit("Error: No .pdf files found in the selected input directory.")
                return

            total = len(path_list)
            self.progress.emit(f"Found {total} PDF(s). Preparing output directories...")

            # Setup target directories inside the output folder
            text_dir = os.path.join(self.output_dir, "Articles-Text")
            abstracts_dir = os.path.join(self.output_dir, "Abstracts")
            images_dir = os.path.join(self.output_dir, "Images")

            os.makedirs(text_dir, exist_ok=True)
            os.makedirs(abstracts_dir, exist_ok=True)
            os.makedirs(images_dir, exist_ok=True)

            processed = 0
            failed = 0

            for idx, p in enumerate(path_list, start=1):
                if self._cancelled:
                    self.progress.emit("Cancelled by user.")
                    break

                index = p.stem
                self.progress.emit(f"[{idx}/{total}] Processing: {p.name}")

                try:
                    doc = pymupdf.open(str(p))

                    # 1. Convert the PDF to plain text
                    content = ""
                    for i in range(doc.page_count):
                        content += doc.load_page(i).get_text() + "\n"

                    # Write the text
                    text_path = os.path.join(text_dir, f"{index}.txt")
                    with open(text_path, "w", encoding="utf-8") as f:
                        f.write(content)

                    # 2. Extract abstract if it does not already exist
                    abs_path = os.path.join(abstracts_dir, f"{index}.txt")
                    if not os.path.exists(abs_path):
                        abstract_start = content.lower().find("abstract")
                        if abstract_start != -1:
                            abstract_end = content.lower().find("introduction", abstract_start)
                            abstract = content[abstract_start:abstract_end].strip() if abstract_end != -1 \
                                else content[abstract_start:].strip()
                            with open(abs_path, "w", encoding="utf-8") as f:
                                f.write(abstract)

                    # 3. Extract images
                    image_list = []
                    img_count = 0
                    end = doc.xref_length()
                    for xref in range(1, end):
                        try:
                            if doc.xref_is_image(xref) is False:
                                continue
                            img = doc.extract_image(xref)
                        except Exception as e:
                            self.progress.emit(f"  -> Error with xref {xref} in {index}: {e}")
                            continue

                        image_list.append((img['image'], img['ext'], img_count))
                        img_count += 1

                    # Save images if found
                    if image_list:
                        article_img_dir = os.path.join(images_dir, index)
                        os.makedirs(article_img_dir, exist_ok=True)
                        for image in image_list:
                            img_path = os.path.join(article_img_dir, f"image{image[2]}.{image[1]}")
                            with open(img_path, "wb") as f:
                                f.write(image[0])

                    doc.close()
                    processed += 1

                except Exception as e:
                    failed += 1
                    self.progress.emit(f"[{idx}/{total}] Failed to process {p.name}: {e}")
                    continue

            msg = (
                "Conversion Completed.\n"
                f"Successfully Processed: {processed}\n"
                f"Failed: {failed}\n"
                f"Output saved to: {self.output_dir}"
            )
            self.finished.emit(msg)

        except Exception as e:
            self.error.emit(f"Critical Error: {e}")


# --------------------------- Main GUI class --------------------------- #

class ManualPDFConversionGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Manual PDF Conversion")
        self.setGeometry(200, 200, 740, 600)

        self._thread = None
        self._worker = None

        app = QApplication.instance()
        app_font_size = app.font().pointSize() if app is not None else 12

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)

        # Font size (global)
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font Size:"))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(8, 32)
        self.font_slider.setValue(app_font_size)
        self.font_slider.setTickInterval(1)
        self.font_value = QLabel(str(self.font_slider.value()))
        self.font_slider.valueChanged.connect(self._on_font_change)
        font_row.addWidget(self.font_slider, 1)
        font_row.addWidget(self.font_value)
        main_layout.addLayout(font_row)

        # Folders Group
        folders_group = QGroupBox("Target Directories")
        folders_layout = QVBoxLayout()

        # Input Layout
        in_layout = QHBoxLayout()
        in_layout.addWidget(QLabel("Input Folder (Contains .pdf files):"))
        self.input_dir_edit = QLineEdit()
        self.input_dir_btn = QPushButton("Browse")
        self.input_dir_btn.clicked.connect(self.browse_input_dir)
        in_layout.addWidget(self.input_dir_edit)
        in_layout.addWidget(self.input_dir_btn)
        folders_layout.addLayout(in_layout)

        # Output Layout
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Output Folder (Converted files saved here):"))
        self.output_dir_edit = QLineEdit()
        self.output_dir_btn = QPushButton("Browse")
        self.output_dir_btn.clicked.connect(self.browse_output_dir)
        out_layout.addWidget(self.output_dir_edit)
        out_layout.addWidget(self.output_dir_btn)
        folders_layout.addLayout(out_layout)

        folders_group.setLayout(folders_layout)
        main_layout.addWidget(folders_group)

        # Run controls
        run_layout = QHBoxLayout()
        self.start_button = QPushButton("Run Conversion")
        self.start_button.clicked.connect(self.start_conversion)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_run)
        self.cancel_button.setEnabled(False)

        run_layout.addWidget(self.start_button)
        run_layout.addWidget(self.cancel_button)
        run_layout.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        main_layout.addLayout(run_layout)

        # Output
        out_header = QHBoxLayout()
        out_header.addWidget(QLabel("Progress / Output"))
        out_header.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.copy_button = QPushButton("Copy")
        self.copy_button.setToolTip("Copy all output to clipboard")
        self.copy_button.clicked.connect(self.copy_output_to_clipboard)
        out_header.addWidget(self.copy_button)
        main_layout.addLayout(out_header)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        main_layout.addWidget(self.output_box)

        # Adopt current app font
        self.setFont(QApplication.instance().font())

    # UI helpers
    def _set_in_progress(self, in_progress: bool):
        self.start_button.setEnabled(not in_progress)
        self.cancel_button.setEnabled(in_progress)
        self.setCursor(Qt.BusyCursor if in_progress else Qt.ArrowCursor)

        self.input_dir_edit.setEnabled(not in_progress)
        self.input_dir_btn.setEnabled(not in_progress)
        self.output_dir_edit.setEnabled(not in_progress)
        self.output_dir_btn.setEnabled(not in_progress)

    def _on_font_change(self, size: int):
        self.font_value.setText(str(size))
        f = QFont()
        f.setPointSize(size)
        QApplication.instance().setFont(f)
        self.setFont(f)

    def browse_input_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Input Folder (PDF files)")
        if path:
            self.input_dir_edit.setText(path)

    def browse_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.output_dir_edit.setText(path)

    def copy_output_to_clipboard(self):
        QApplication.clipboard().setText(self.output_box.toPlainText())
        self.output_box.append("Output copied to clipboard.")

    # Worker wiring
    def start_conversion(self):
        if self._thread and self._thread.isRunning():
            self.output_box.append("Another run is still in progress. Please wait or click Cancel.")
            return

        input_dir = self.input_dir_edit.text().strip()
        output_dir = self.output_dir_edit.text().strip()

        self.output_box.append("Starting PDF conversion and extraction...")
        self._set_in_progress(True)

        self._worker = ConversionWorker(input_dir=input_dir, output_dir=output_dir)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        # Cleanup
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(lambda: self._set_in_progress(False))
        self._thread.finished.connect(lambda: setattr(self, "_worker", None))
        self._thread.finished.connect(lambda: setattr(self, "_thread", None))

        self._thread.start()

    def cancel_run(self):
        if self._worker is not None:
            self.output_box.append("Cancel requested...")
            self._worker.cancel()

    # Worker signal handlers
    def _on_progress(self, msg: str):
        self.output_box.append(msg)

    def _on_finished(self, msg: str):
        self.output_box.append("\n" + msg + "\n")

    def _on_error(self, msg: str):
        self.output_box.append(msg + "\n")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if app.font().pointSize() <= 0:
        f = QFont()
        f.setPointSize(12)
        app.setFont(f)

    window = ManualPDFConversionGUI()
    window.show()
    sys.exit(app.exec_())