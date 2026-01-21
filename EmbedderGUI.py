# PyQtArticleEmbedder.py
import sys, os, json
from typing import List, Tuple

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QComboBox,
    QSlider, QGroupBox, QCheckBox, QFileDialog, QToolButton, QStyle,
    QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt5.QtGui import QFont

from openai import OpenAI


# --------------------- Embedding helpers --------------------- #

def _normalize_ws(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()

def _chunk_text_by_chars(text: str, max_chars: int = 12000, overlap: int = 400) -> List[str]:
    """
    Character-based chunking (simple + reliable). Overlap helps preserve continuity.
    """
    text = _normalize_ws(text)
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(0, end - overlap)

    return chunks

def _mean_pool(vectors: List[List[float]]) -> List[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    out = [0.0] * dim
    for v in vectors:
        if len(v) != dim:
            raise ValueError("Embedding dimension mismatch while mean-pooling.")
        for i in range(dim):
            out[i] += float(v[i])
    denom = float(len(vectors))
    return [x / denom for x in out]


# --------------------- Worker for background embedding calls --------------------- #

class EmbeddingWorker(QObject):
    finished = pyqtSignal(str)   # final status message
    error = pyqtSignal(str)      # error message
    progress = pyqtSignal(str)   # progress updates

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        input_dir: str,
        output_dir: str,
        overwrite: bool,
        max_articles: int,
        chunk_max_chars: int,
        chunk_overlap: int,
        prefix_header: bool
    ):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.overwrite = overwrite
        self.max_articles = max_articles
        self.chunk_max_chars = chunk_max_chars
        self.chunk_overlap = chunk_overlap
        self.prefix_header = prefix_header

        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _get_embedding(self, client: OpenAI, text: str) -> List[float]:
        text = text.replace("\n", " ")
        return client.embeddings.create(input=[text], model=self.model).data[0].embedding

    def _build_embedding_string(self, filename: str, article_text: str) -> str:
        """
        If prefix_header is enabled, prepend a short identifier header.
        Otherwise, embed raw article text only.
        """
        article_text = _normalize_ws(article_text)
        if not self.prefix_header:
            return article_text
        return f"Article: {filename}\nArticle Text:\n{article_text}"

    def _discover_input_files(self) -> List[str]:
        # Discover .txt files (sorted for stability)
        names = sorted([
            n for n in os.listdir(self.input_dir)
            if os.path.isfile(os.path.join(self.input_dir, n)) and n.lower().endswith(".txt")
        ])
        if self.max_articles and self.max_articles > 0:
            names = names[: self.max_articles]
        return names

    def _make_output_path(self, input_filename: str) -> str:
        """
        Save embedding JSON to output_dir using the same base filename:
          Input:  SomePaper.txt
          Output: <output_dir>/SomePaper.txt
        This mirrors your original style of storing embeddings as JSON in .txt files.
        """
        base = os.path.splitext(input_filename)[0]
        return os.path.join(self.output_dir, f"{base}.txt")

    def run(self):
        try:
            # Validation
            if not self.api_key:
                self.error.emit("Error: Please provide an OpenAI API key.")
                return
            if not self.input_dir:
                self.error.emit("Error: Please select an input folder of article .txt files.")
                return
            if not os.path.isdir(self.input_dir):
                self.error.emit(f"Error: Input directory not found: {self.input_dir}")
                return
            if not self.output_dir:
                self.error.emit("Error: Please select an output folder.")
                return
            if not os.path.isdir(self.output_dir):
                self.error.emit(f"Error: Output directory not found: {self.output_dir}")
                return

            client = OpenAI(api_key=self.api_key, timeout=60)

            self.progress.emit("Scanning input directory for .txt files...")
            names = self._discover_input_files()

            if not names:
                self.error.emit("Error: No .txt files found in the selected input directory.")
                return

            total = len(names)
            self.progress.emit(f"Found {total} file(s). Output: {self.output_dir}")

            created = 0
            skipped = 0
            failed = 0
            chunked = 0

            for idx, fname in enumerate(names, start=1):
                if self._cancelled:
                    self.progress.emit("Cancelled by user.")
                    break

                in_path = os.path.join(self.input_dir, fname)
                out_path = self._make_output_path(fname)

                # Skip if exists and not overwriting
                if (not self.overwrite) and os.path.isfile(out_path):
                    skipped += 1
                    self.progress.emit(f"[{idx}/{total}] Skipping (exists): {fname}")
                    continue

                self.progress.emit(f"[{idx}/{total}] Reading: {fname}")
                try:
                    with open(in_path, "r", encoding="utf-8", errors="replace") as f:
                        article_text = f.read()
                except Exception as e:
                    failed += 1
                    self.progress.emit(f"[{idx}/{total}] Failed to read {fname}: {e}")
                    continue

                embed_string = self._build_embedding_string(fname, article_text)

                chunks = _chunk_text_by_chars(
                    embed_string,
                    max_chars=self.chunk_max_chars,
                    overlap=self.chunk_overlap
                )
                if not chunks:
                    failed += 1
                    self.progress.emit(f"[{idx}/{total}] Empty text after normalization: {fname}")
                    continue

                try:
                    if len(chunks) == 1:
                        self.progress.emit(f"[{idx}/{total}] Creating embedding...")
                        emb = self._get_embedding(client, chunks[0])
                    else:
                        chunked += 1
                        self.progress.emit(f"[{idx}/{total}] Creating embeddings ({len(chunks)} chunks)...")
                        vectors = []
                        for ci, chunk in enumerate(chunks, start=1):
                            if self._cancelled:
                                break
                            self.progress.emit(f"  Chunk {ci}/{len(chunks)}")
                            vectors.append(self._get_embedding(client, chunk))
                        if self._cancelled:
                            self.progress.emit("Cancelled by user.")
                            break
                        emb = _mean_pool(vectors)

                    # Save embedding JSON directly to output_dir
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(json.dumps(emb))

                    created += 1
                    self.progress.emit(f"[{idx}/{total}] Saved embedding: {os.path.basename(out_path)}")

                except Exception as e:
                    failed += 1
                    self.progress.emit(f"[{idx}/{total}] Failed to embed {fname}: {e}")
                    continue

            msg = (
                "Done.\n"
                f"Created: {created}\n"
                f"Skipped: {skipped}\n"
                f"Failed: {failed}\n"
                f"Chunked (mean-pooled): {chunked}\n"
                f"Output folder: {self.output_dir}"
            )
            self.finished.emit(msg)

        except Exception as e:
            self.error.emit(f"Error: {e}")


# --------------------------- Main GUI class --------------------------- #

class ArticleEmbeddingGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Article Embedding Generator (Manual)")
        self.setGeometry(200, 200, 740, 820)

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

        # API Key
        api_group = QGroupBox("OpenAI API Key")
        api_layout = QHBoxLayout()
        self.api_key_field = QLineEdit()
        self.api_key_field.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(self.api_key_field)
        self.toggle_checkbox = QCheckBox("Show")
        self.toggle_checkbox.stateChanged.connect(self.toggle_password_visibility)
        api_layout.addWidget(self.toggle_checkbox)
        api_group.setLayout(api_layout)
        main_layout.addWidget(api_group)

        # Settings
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout()

        # Model dropdown
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Embedding Model:"))
        self.model_dropdown = QComboBox()
        self.model_dropdown.addItems([
            "text-embedding-ada-002",
            "text-embedding-3-small",
            "text-embedding-3-large"

        ])
        model_layout.addWidget(self.model_dropdown)

        info_btn = QToolButton()
        info_btn.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        info_btn.setAutoRaise(True)
        info_btn.setToolTip(
            "Long files are chunked and mean-pooled.\n"
            "Embeddings are saved as JSON arrays in the selected output folder."
        )
        model_layout.addWidget(info_btn)
        settings_layout.addLayout(model_layout)

        # Overwrite checkbox
        ow_layout = QHBoxLayout()
        self.overwrite_checkbox = QCheckBox("Overwrite existing embeddings")
        self.overwrite_checkbox.setChecked(False)
        ow_layout.addWidget(self.overwrite_checkbox)
        ow_layout.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        settings_layout.addLayout(ow_layout)

        # Prefix header checkbox
        prefix_layout = QHBoxLayout()
        self.prefix_checkbox = QCheckBox("Prefix embedding string with an 'Article: <filename>' header")
        self.prefix_checkbox.setChecked(True)
        prefix_layout.addWidget(self.prefix_checkbox)
        prefix_layout.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        settings_layout.addLayout(prefix_layout)

        # Max Articles slider
        max_articles_layout = QHBoxLayout()
        max_articles_layout.addWidget(QLabel("Max Articles (0 = no limit):"))
        self.max_articles_slider = QSlider(Qt.Horizontal)
        self.max_articles_slider.setMinimum(0)
        self.max_articles_slider.setMaximum(500)
        self.max_articles_slider.setValue(0)
        self.max_articles_slider.setTickInterval(50)
        self.max_articles_slider.setSingleStep(1)
        self.max_articles_slider.valueChanged.connect(self.update_max_articles_label)
        max_articles_layout.addWidget(self.max_articles_slider)
        self.max_articles_value_label = QLabel("0")
        self.max_articles_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        max_articles_layout.addWidget(self.max_articles_value_label)
        settings_layout.addLayout(max_articles_layout)

        # Chunk size slider (chars)
        chunk_layout = QHBoxLayout()
        chunk_layout.addWidget(QLabel("Chunk Max Chars:"))
        self.chunk_slider = QSlider(Qt.Horizontal)
        self.chunk_slider.setMinimum(4000)
        self.chunk_slider.setMaximum(20000)
        self.chunk_slider.setValue(12000)
        self.chunk_slider.setTickInterval(2000)
        self.chunk_slider.setSingleStep(500)
        self.chunk_slider.valueChanged.connect(self.update_chunk_label)
        chunk_layout.addWidget(self.chunk_slider)
        self.chunk_value_label = QLabel(str(self.chunk_slider.value()))
        self.chunk_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        chunk_layout.addWidget(self.chunk_value_label)
        settings_layout.addLayout(chunk_layout)

        # Chunk overlap slider (chars)
        overlap_layout = QHBoxLayout()
        overlap_layout.addWidget(QLabel("Chunk Overlap Chars:"))
        self.overlap_slider = QSlider(Qt.Horizontal)
        self.overlap_slider.setMinimum(0)
        self.overlap_slider.setMaximum(2000)
        self.overlap_slider.setValue(400)
        self.overlap_slider.setTickInterval(200)
        self.overlap_slider.setSingleStep(50)
        self.overlap_slider.valueChanged.connect(self.update_overlap_label)
        overlap_layout.addWidget(self.overlap_slider)
        self.overlap_value_label = QLabel(str(self.overlap_slider.value()))
        self.overlap_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        overlap_layout.addWidget(self.overlap_value_label)
        settings_layout.addLayout(overlap_layout)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # Folders
        folders_group = QGroupBox("Folders")
        folders_layout = QVBoxLayout()

        in_layout = QHBoxLayout()
        in_layout.addWidget(QLabel("Input folder (article .txt files):"))
        self.input_dir_edit = QLineEdit()
        self.input_dir_btn = QPushButton("Browse")
        self.input_dir_btn.clicked.connect(self.browse_input_dir)
        in_layout.addWidget(self.input_dir_edit)
        in_layout.addWidget(self.input_dir_btn)
        folders_layout.addLayout(in_layout)

        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Output folder (embeddings saved here):"))
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
        self.start_button = QPushButton("Generate Embeddings")
        self.start_button.clicked.connect(self.start_embedding_run)
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

        # Init labels
        self.update_max_articles_label(self.max_articles_slider.value())
        self.update_chunk_label(self.chunk_slider.value())
        self.update_overlap_label(self.overlap_slider.value())

        # Adopt current app font
        self.setFont(QApplication.instance().font())

    # UI helpers
    def _set_in_progress(self, in_progress: bool):
        self.start_button.setEnabled(not in_progress)
        self.cancel_button.setEnabled(in_progress)
        self.setCursor(Qt.BusyCursor if in_progress else Qt.ArrowCursor)

        self.api_key_field.setEnabled(not in_progress)
        self.model_dropdown.setEnabled(not in_progress)
        self.input_dir_edit.setEnabled(not in_progress)
        self.input_dir_btn.setEnabled(not in_progress)
        self.output_dir_edit.setEnabled(not in_progress)
        self.output_dir_btn.setEnabled(not in_progress)
        self.overwrite_checkbox.setEnabled(not in_progress)
        self.prefix_checkbox.setEnabled(not in_progress)
        self.max_articles_slider.setEnabled(not in_progress)
        self.chunk_slider.setEnabled(not in_progress)
        self.overlap_slider.setEnabled(not in_progress)

    def _on_font_change(self, size: int):
        self.font_value.setText(str(size))
        f = QFont()
        f.setPointSize(size)
        QApplication.instance().setFont(f)
        self.setFont(f)

    def toggle_password_visibility(self):
        self.api_key_field.setEchoMode(
            QLineEdit.Normal if self.toggle_checkbox.isChecked() else QLineEdit.Password
        )

    def update_max_articles_label(self, value: int):
        self.max_articles_value_label.setText(str(value))

    def update_chunk_label(self, value: int):
        self.chunk_value_label.setText(str(value))

    def update_overlap_label(self, value: int):
        self.overlap_value_label.setText(str(value))

    def browse_input_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Input Folder (Article .txt files)")
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
    def start_embedding_run(self):
        if self._thread and self._thread.isRunning():
            self.output_box.append("Another run is still in progress. Please wait or click Cancel.")
            return

        api_key = self.api_key_field.text().strip()
        model = self.model_dropdown.currentText().strip()
        input_dir = self.input_dir_edit.text().strip()
        output_dir = self.output_dir_edit.text().strip()
        overwrite = self.overwrite_checkbox.isChecked()
        max_articles = self.max_articles_slider.value()
        chunk_max_chars = self.chunk_slider.value()
        chunk_overlap = self.overlap_slider.value()
        prefix_header = self.prefix_checkbox.isChecked()

        self.output_box.append("Starting embedding generation...")
        self._set_in_progress(True)

        self._worker = EmbeddingWorker(
            api_key=api_key,
            model=model,
            input_dir=input_dir,
            output_dir=output_dir,
            overwrite=overwrite,
            max_articles=max_articles,
            chunk_max_chars=chunk_max_chars,
            chunk_overlap=chunk_overlap,
            prefix_header=prefix_header
        )
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

    window = ArticleEmbeddingGUI()
    window.show()
    sys.exit(app.exec_())
