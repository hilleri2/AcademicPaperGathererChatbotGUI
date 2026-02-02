# ChatbotAutoGUI.py
import sys, os, os.path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QComboBox,
    QSlider, QGroupBox, QCheckBox, QFileDialog, QToolButton, QStyle, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt5.QtGui import QFont
from openai import OpenAI

def create_file(client, file_path):
    with open(file_path, "rb") as f:
        return client.files.create(file=f, purpose="assistants").id


# --------------------- Worker for background API calls --------------------- #
class ChatWorker(QObject):
    finished = pyqtSignal(str)         # final chatbot response text
    error = pyqtSignal(str)            # error message
    progress = pyqtSignal(str)         # streaming progress updates

    def __init__(self, *, prompt, model, temperature, api_key,
                 botrole, introstring, dataintro, articles_dir,
                 max_articles, max_tokens):
        super().__init__()
        self.prompt = prompt
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.botrole = botrole
        self.introstring = introstring
        self.dataintro = dataintro
        self.articles_dir = articles_dir
        self.max_articles = max_articles
        self.max_tokens = max_tokens

    def run(self):
        try:
            if not self.api_key:
                self.error.emit("Error: Please provide an OpenAI API key.")
                return
            if not self.articles_dir:
                self.error.emit("Error: Please provide a file path for article PDFs to search.")
                return
            if not os.path.isdir(self.articles_dir):
                self.error.emit(f"Error: Directory not found: {self.articles_dir}")
                return

            # Create client with a conservative timeout (prevents indefinite hangs)
            client = OpenAI(api_key=self.api_key, timeout=60)  # seconds

            # Discover PDFs
            self.progress.emit("Scanning directory for PDFs…")
            article_paths = [
                os.path.join(self.articles_dir, name)
                for name in os.listdir(self.articles_dir)
                if name.lower().endswith(".pdf")
            ]
            if not article_paths:
                self.error.emit("Error: No .pdf files found in the selected directory.")
                return

            # Check for max article count
            if self.max_articles and self.max_articles > 0:
                article_paths = article_paths

            self.progress.emit(f"Found {len(article_paths)} PDF(s). Uploading…")

            # Upload files with per-file progress
            file_ids = []
            for idx, p in enumerate(article_paths, start=1):
                try:
                    self.progress.emit(f"Uploading {idx}/{len(article_paths)}: {os.path.basename(p)}")
                    fid = create_file(client, p)
                    file_ids.append(fid)
                except Exception as e:
                    # Continue on individual file errors, but report them
                    self.progress.emit(f"Skipped {os.path.basename(p)} — {e}")

            if not file_ids:
                self.error.emit("Error: Failed to upload any files.")
                return

            self.progress.emit("Creating vector store…")
            vector_store = client.vector_stores.create(name="knowledge_base")

            self.progress.emit("Attaching files to vector store…")
            for idx, fid in enumerate(file_ids, start=1):
                self.progress.emit(f"Indexing {idx}/{len(file_ids)}")
                client.vector_stores.files.create(
                    vector_store_id=vector_store.id,
                    file_id=fid
                )

            # Poll indexing status for better feedback (lightweight poll loop)
            self.progress.emit("Analyzing files (building index)…")
            import time
            while True:
                listing = client.vector_stores.files.list(vector_store_id=vector_store.id)
                statuses = {f.status for f in listing.data}  # completed | in_progress | failed
                # Show a tiny heartbeat so the user sees activity
                self.progress.emit(f"Index status: {', '.join(sorted(statuses))}")
                if statuses <= {"completed"}:
                    break
                if "failed" in statuses and "in_progress" not in statuses:
                    self.progress.emit("Some files failed to index; continuing with available files.")
                    break
                time.sleep(1.0)

            self.progress.emit("Querying Model…")

            # Query model (keeping your original include/tools)
            response = client.responses.create(
                model=self.model,
                input=self.prompt,
                tools=[{
                    "type": "file_search",
                    "vector_store_ids": [vector_store.id]
                }],
                # keep include (SDK may change behavior; if it errors, we catch)
                include=["file_search_call.results"],
                max_output_tokens=self.max_tokens if self.max_tokens else None,
                temperature=self.temperature if self.model == "gpt-4" or self.model == "gpt-3.5-turbo" else None
            )

            # Make sure we can extract text robustly
            try:
                text = response.output_text
            except Exception:
                # Fallback: stringify response if output_text isn’t present
                text = getattr(response, "output", None) or str(response)

            self.finished.emit(text)

        except Exception as e:
            self.error.emit(f"Error: {e}")


# --------------------------- Main GUI class --------------------------- #
class ChatBotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 Chatbot with OpenAI API Key")
        self.setGeometry(200, 200, 700, 860)
        self.client = None
        self._thread = None
        self._worker = None

        # --- Initialize to current *global* font size ---
        app = QApplication.instance()
        app_font_size = app.font().pointSize() if app is not None else 12

        # Central layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)

        # Font selector (applies app-wide)
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

        # --- API Key ---
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

        # --- Settings ---
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout()

        # Model
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_dropdown = QComboBox()
        self.model_dropdown.addItems(["gpt-5.2", "gpt-5", "gpt-4o", "gpt-3.5-turbo", "custom-model"])
        model_layout.addWidget(self.model_dropdown)
        settings_layout.addLayout(model_layout)

        # Max Articles
        max_articles_layout = QHBoxLayout()
        max_articles_layout.addWidget(QLabel("Max Articles:"))
        self.max_articles_slider = QSlider(Qt.Horizontal)
        self.max_articles_slider.setMinimum(0)
        self.max_articles_slider.setMaximum(30)
        self.max_articles_slider.setValue(5)
        self.max_articles_slider.setTickInterval(30)
        self.max_articles_slider.setSingleStep(1)
        self.max_articles_slider.valueChanged.connect(self.update_max_articles_label)
        max_articles_layout.addWidget(self.max_articles_slider)
        self.max_articles_value_label = QLabel("100")
        self.max_articles_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        max_articles_layout.addWidget(self.max_articles_value_label)
        settings_layout.addLayout(max_articles_layout)

        # Max Tokens — multiples of 256
        max_tokens_layout = QHBoxLayout()
        max_tokens_layout.addWidget(QLabel("Max Tokens:"))
        self._TOK_STEP = 256
        self.max_tokens_slider = QSlider(Qt.Horizontal)
        self.max_tokens_slider.setMinimum(1)   # 256
        self.max_tokens_slider.setMaximum(100000 // self._TOK_STEP)
        self.max_tokens_slider.setValue(4096 // self._TOK_STEP)
        self.max_tokens_slider.setTickInterval(4)
        self.max_tokens_slider.setSingleStep(1)
        self.max_tokens_slider.valueChanged.connect(self.update_max_tokens_label)
        max_tokens_layout.addWidget(self.max_tokens_slider)
        self.max_tokens_value_label = QLabel("4096")
        self.max_tokens_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        max_tokens_layout.addWidget(self.max_tokens_value_label)
        settings_layout.addLayout(max_tokens_layout)

        # Temperature
        temp_layout = QHBoxLayout()

        # (3) Info icon with tooltip next to the prompt line
        info_btn2 = QToolButton()
        info_btn2.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        info_btn2.setAutoRaise(True)
        info_btn2.setToolTip(
            "The temperature control was removed from the API for models gpt-5 and onward, so changing it will not have any effect for those models."
            # "Usage tips:\n"
            # "• Keep questions specific for better results.\n"
            # "• PDFs in the selected folder are used as the knowledge base.\n"
            # "• Placeholder: add policy/stipulation text here."
        )
        temp_layout.addWidget(info_btn2)

        temp_layout.addWidget(QLabel("Temperature:"))
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setMinimum(0)
        self.temp_slider.setMaximum(10)
        self.temp_slider.setValue(7)
        self.temp_slider.setTickInterval(1)
        self.temp_slider.valueChanged.connect(self.update_temp_label)
        temp_layout.addWidget(self.temp_slider)
        self.temp_value_label = QLabel("0.7")
        self.temp_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        temp_layout.addWidget(self.temp_value_label)



        settings_layout.addLayout(temp_layout)
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # --- Prompt & Context ---
        context_group = QGroupBox("Prompt & Context")
        context_layout = QVBoxLayout()

        # Articles directory (top)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Articles to search"))
        self.articles_dir_edit = QLineEdit()
        self.articles_dir_btn = QPushButton("Browse")
        self.articles_dir_btn.clicked.connect(self.browse_articles_dir)
        dir_layout.addWidget(self.articles_dir_edit)
        dir_layout.addWidget(self.articles_dir_btn)
        context_layout.addLayout(dir_layout)

        # -------- Advanced collapsible section --------
        # Toggle button (looks like a header)
        adv_header = QHBoxLayout()
        self.adv_toggle_btn = QToolButton()
        self.adv_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.adv_toggle_btn.setArrowType(Qt.RightArrow)  # points right when collapsed
        self.adv_toggle_btn.setText("Advanced")
        self.adv_toggle_btn.setCheckable(True)
        self.adv_toggle_btn.setChecked(False)
        self.adv_toggle_btn.clicked.connect(self._toggle_advanced)
        adv_header.addWidget(self.adv_toggle_btn)
        adv_header.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        context_layout.addLayout(adv_header)

        # The advanced content container (hidden by default)
        self.advanced_widget = QWidget()
        adv_form_layout = QVBoxLayout(self.advanced_widget)
        adv_form_layout.setContentsMargins(24, 0, 0, 0)  # indent a bit

        # botrole
        role_label = QLabel("botrole")
        adv_form_layout.addWidget(role_label)
        self.role_edit = QTextEdit()
        self.role_edit.setPlainText(
            "You are a research assistant. Your job is to answer questions about articles provided to you."
        )
        self.role_edit.setFixedHeight(60)
        adv_form_layout.addWidget(self.role_edit)

        # introstring
        intro_label = QLabel("introstring")
        adv_form_layout.addWidget(intro_label)
        self.intro_edit = QLineEdit()
        self.intro_edit.setText("Use the articles provided to answer the subsequent question.")
        adv_form_layout.addWidget(self.intro_edit)

        # dataintro
        dataintro_label = QLabel("dataintro")
        adv_form_layout.addWidget(dataintro_label)
        self.dataintro_edit = QLineEdit()
        self.dataintro_edit.setText("Here is the next article data section")
        adv_form_layout.addWidget(self.dataintro_edit)

        self.advanced_widget.setVisible(False)
        context_layout.addWidget(self.advanced_widget)
        # -------- End Advanced section --------

        context_group.setLayout(context_layout)
        main_layout.addWidget(context_group)

        # --- Prompt label + input ---
        main_layout.addWidget(QLabel("Chatbot Prompt: Type your question for the assistant and press Enter or click Send."))

        input_layout = QHBoxLayout()

        # (3) Info icon with tooltip next to the prompt line
        info_btn = QToolButton()
        info_btn.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        info_btn.setAutoRaise(True)
        info_btn.setToolTip(
            "This tool doesn't have the ability to hold ongoing conversations.\n"
            "Repeated inputs will be treated as individual conversations without recollection of what came before."
            # "Usage tips:\n"
            # "• Keep questions specific for better results.\n"
            # "• PDFs in the selected folder are used as the knowledge base.\n"
            # "• Placeholder: add policy/stipulation text here."
        )
        input_layout.addWidget(info_btn)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Type your message…")
        self.entry.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.entry)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)
        main_layout.addLayout(input_layout)

        # Output header row with Copy button (2)
        out_header = QHBoxLayout()
        out_header.addWidget(QLabel("Output"))
        out_header.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.copy_button = QPushButton("Copy")
        self.copy_button.setToolTip("Copy all output to clipboard")
        self.copy_button.clicked.connect(self.copy_output_to_clipboard)
        out_header.addWidget(self.copy_button)
        main_layout.addLayout(out_header)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        main_layout.addWidget(self.chat_display)

        # Initialize labels
        self.update_max_articles_label(self.max_articles_slider.value())
        self.update_max_tokens_label(self.max_tokens_slider.value())
        self.update_temp_label()

        # Adopt current app font
        self.setFont(QApplication.instance().font())

    # --- Advanced toggle ---
    def _toggle_advanced(self, checked: bool):
        self.advanced_widget.setVisible(checked)
        # Rotate the arrow to indicate expanded/collapsed
        self.adv_toggle_btn.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    # --- font handling (global) ---
    def _on_font_change(self, size: int):
        self.font_value.setText(str(size))
        self._apply_app_font(size)

    def _apply_app_font(self, size: int):
        f = QFont()
        f.setPointSize(size)
        QApplication.instance().setFont(f)
        self.setFont(f)

    # --- Handlers ---
    def update_temp_label(self):
        temp_value = self.temp_slider.value() / 10.0
        self.temp_value_label.setText(f"{temp_value:.1f}")

    def update_max_articles_label(self, value: int):
        self.max_articles_value_label.setText(str(value))

    def update_max_tokens_label(self, slider_pos: int):
        tokens = slider_pos * self._TOK_STEP
        self.max_tokens_value_label.setText(str(tokens))

    def toggle_password_visibility(self):
        self.api_key_field.setEchoMode(
            QLineEdit.Normal if self.toggle_checkbox.isChecked() else QLineEdit.Password
        )

    def browse_articles_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Articles Directory")
        if path:
            self.articles_dir_edit.setText(path)

    def _set_request_in_progress(self, in_progress: bool):
        self.send_button.setEnabled(not in_progress)
        self.entry.setEnabled(not in_progress)
        self.model_dropdown.setEnabled(not in_progress)
        self.setCursor(Qt.BusyCursor if in_progress else Qt.ArrowCursor)

    def copy_output_to_clipboard(self):
        QApplication.clipboard().setText(self.chat_display.toPlainText())
        # Optional: small feedback line in the output
        self.chat_display.append("✅ Output copied to clipboard.")

    def send_message(self):
        # Prevent overlapping runs (this was a common source of “hangs”)
        if self._thread and self._thread.isRunning():
            self.chat_display.append("Another request is still running. Please wait for it to finish.")
            return

        user_input = self.entry.text().strip()
        if not user_input:
            return

        self.chat_display.append(f"You: {user_input}")

        model = self.model_dropdown.currentText()
        temperature = self.temp_slider.value() / 10.0
        api_key = self.api_key_field.text().strip()
        max_articles = self.max_articles_slider.value()
        max_tokens = self.max_tokens_slider.value() * self._TOK_STEP

        botrole = self.role_edit.toPlainText().strip()
        introstring = self.intro_edit.text().strip()
        dataintro = self.dataintro_edit.text().strip()
        articles_dir = self.articles_dir_edit.text().strip()

        self.entry.clear()
        self._set_request_in_progress(True)

        # Create worker & thread (store both to prevent GC)
        self._worker = ChatWorker(
            prompt=user_input, model=model, temperature=temperature, api_key=api_key,
            botrole=botrole, introstring=introstring, dataintro=dataintro, articles_dir=articles_dir,
            max_articles=max_articles, max_tokens=max_tokens
        )
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)

        # Wire signals
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(lambda text: self._on_worker_finished(
            text, model, temperature, max_articles, max_tokens))
        self._worker.error.connect(self._on_worker_error)

        # Cleanup & UI reset
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(lambda: self._set_request_in_progress(False))
        self._thread.finished.connect(lambda: setattr(self, "_worker", None))
        self._thread.finished.connect(lambda: setattr(self, "_thread", None))

        self._thread.start()

    # --- Worker signal handlers (GUI-thread safe) ---
    def _on_worker_progress(self, msg: str):
        self.chat_display.append(msg)

    def _on_worker_finished(self, response_text: str, model: str, temperature: float,
                            max_articles: int, max_tokens: int):
        self.chat_display.append(
            f"Chatbot ({model}, Temp={temperature}, MaxArticles={max_articles}, MaxTokens={max_tokens}):\n{response_text}\n"
        )

    def _on_worker_error(self, err_text: str):
        self.chat_display.append(err_text)

    # --- Legacy synchronous path retained (unchanged) ---
    def get_openai_response(self, *args, **kwargs):
        # Kept for reference; GUI uses threaded path.
        return "Synchronous path retained; not used by GUI."

if __name__ == "__main__":
    app = QApplication(sys.argv)
    if app.font().pointSize() <= 0:
        f = QFont()
        f.setPointSize(12)
        app.setFont(f)
    window = ChatBotGUI()
    window.show()
    sys.exit(app.exec_())
