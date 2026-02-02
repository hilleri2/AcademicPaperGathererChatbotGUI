# PyQtEmbeddingChat.py
import sys, os, json, math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QComboBox,
    QSlider, QGroupBox, QCheckBox, QFileDialog, QToolButton, QStyle,
    QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt5.QtGui import QFont

from openai import OpenAI


# --------------------- Token counting (tiktoken optional) --------------------- #

def num_tokens(text: str, model: str = "gpt-5") -> int:
    """
    Best-effort token estimation.
    If tiktoken is installed, use it. Otherwise approximate.
    """
    try:
        import tiktoken  # type: ignore
        try:
            enc = tiktoken.encoding_for_model(model)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Rough approximation: 1 token ~ 4 characters (English-ish)
        # Keep conservative so we don't overflow too often.
        return max(1, len(text) // 4)


# --------------------- Similarity helpers --------------------- #

def cosine_similarity(a: List[float], b: List[float]) -> float:
    # Guard
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(len(a)):
        ai = float(a[i])
        bi = float(b[i])
        dot += ai * bi
        na += ai * ai
        nb += bi * bi
    denom = math.sqrt(na) * math.sqrt(nb)
    if denom == 0.0:
        return -1.0
    return dot / denom


# --------------------- Articles structures --------------------- #

@dataclass
class ArticlesItem:
    key: str          # base filename
    text: str
    embedding: List[float]


def is_probably_embedding_json_file(path: str) -> bool:
    """
    Lightweight heuristic for "embedding files are JSON arrays".
    Useful if user accidentally points both dirs to the same folder.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(64).lstrip()
        return head.startswith("[")  # embedding vectors are JSON arrays
    except Exception:
        return False


def load_Articles(
    text_dir: str,
    embedding_dir: str,
    *,
    dedup: bool,
    dedup_tail_chars: int = 50,
    max_files: int = 0,
    progress_cb=None
) -> Tuple[List[ArticlesItem], Dict[str, int]]:
    """
    Load Articles by matching base filenames:
      text_dir:      <base>.txt
      embedding_dir: <base>.txt (JSON list of floats)
    Returns (items, stats).
    """
    if progress_cb:
        progress_cb("Scanning directories...")

    # Gather candidates
    text_names = sorted([
        n for n in os.listdir(text_dir)
        if os.path.isfile(os.path.join(text_dir, n)) and n.lower().endswith(".txt")
    ])
    emb_names = sorted([
        n for n in os.listdir(embedding_dir)
        if os.path.isfile(os.path.join(embedding_dir, n)) and n.lower().endswith(".txt")
    ])

    # Optional: avoid treating JSON embedding files as text if same dir used
    # by filtering text_names that look like embeddings
    filtered_text_names = []
    for n in text_names:
        p = os.path.join(text_dir, n)
        if is_probably_embedding_json_file(p):
            continue
        filtered_text_names.append(n)
    text_names = filtered_text_names

    # Respect max_files (0 => no limit)
    if max_files and max_files > 0:
        text_names = text_names[:max_files]

    emb_set = set(emb_names)

    items: List[ArticlesItem] = []
    stats = {
        "text_files_seen": len(text_names),
        "embedding_files_seen": len(emb_names),
        "matched": 0,
        "missing_embedding": 0,
        "failed_parse": 0,
        "duplicates_skipped": 0,
    }

    dedup_dict: Dict[str, int] = {}

    for idx, text_name in enumerate(text_names, start=1):
        
        base = os.path.splitext(text_name)[0]
        emb_name = f"{base}.txt"
        if emb_name not in emb_set:
            stats["missing_embedding"] += 1
            if progress_cb and (idx % 25 == 0 or idx == 1):
                progress_cb(f"Loading Articles... {idx}/{len(text_names)} (missing embeddings so far: {stats['missing_embedding']})")
            continue

        text_path = os.path.join(text_dir, text_name)
        emb_path = os.path.join(embedding_dir, emb_name)

        try:
            with open(text_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read().strip()
        except Exception:
            stats["failed_parse"] += 1
            continue

        try:
            with open(emb_path, "r", encoding="utf-8", errors="replace") as f:
                emb = json.loads(f.read())
            # validate
            if not isinstance(emb, list) or not emb or not isinstance(emb[0], (int, float)):
                raise ValueError("Embedding file did not contain a JSON list of numbers.")
        except Exception:
            stats["failed_parse"] += 1
            continue

        # Duplicate protection similar to your approach
        if dedup:
            tail = text[-dedup_tail_chars:] if len(text) >= dedup_tail_chars else text
            if tail in dedup_dict:
                dedup_dict[tail] += 1
                stats["duplicates_skipped"] += 1
                continue
            dedup_dict[tail] = 1

        items.append(ArticlesItem(key=base, text=text, embedding=emb))
        stats["matched"] += 1

        if progress_cb and (idx % 25 == 0 or idx == 1 or idx == len(text_names)):
            progress_cb(f"Loading Articles... {idx}/{len(text_names)} (matched: {stats['matched']})")
    
    return items, stats


# --------------------- Retrieval + Prompt assembly --------------------- #

def strings_ranked_by_relatedness(
    client: OpenAI,
    query: str,
    items: List[ArticlesItem],
    *,
    embedding_model: str,
    top_n: int
) -> Tuple[List[str], List[float]]:
    query_emb = client.embeddings.create(model=embedding_model, input=query).data[0].embedding
    scored = [(it.text, cosine_similarity(query_emb, it.embedding)) for it in items]
    scored.sort(key=lambda x: x[1], reverse=True)
    strings, rels = zip(*scored) if scored else ([], [])
    return list(strings[:top_n]), list(rels[:top_n])


def query_message(
    client: OpenAI,
    articlequery: str,
    botquery: str,
    items: List[ArticlesItem],
    *,
    chat_model: str,
    embedding_model: str,
    token_budget: int,
    introstring: str,
    dataintro: str,
    nmax: int
) -> str:
    strings, _rels = strings_ranked_by_relatedness(
        client,
        articlequery,
        items,
        embedding_model=embedding_model,
        top_n=nmax
    )

    introduction = introstring.strip()
    question = f"\n\nQuestion: {botquery.strip()}"
    message = introduction

    for s in strings:
        next_article = f'\n\n{dataintro}:\n"""\n{s}\n"""'
        if num_tokens(message + next_article + question, model=chat_model) > token_budget:
            break
        message += next_article

    return message + question


def ask(
    client: OpenAI,
    articlequery: str,
    botquery: str,
    items: List[ArticlesItem],
    *,
    chat_model: str,
    embedding_model: str,
    token_budget: int,
    botrole: str,
    introstring: str,
    dataintro: str,
    nmax: int,
    temperature: float
) -> str:
    msg = query_message(
        client,
        articlequery,
        botquery,
        items,
        chat_model=chat_model,
        embedding_model=embedding_model,
        token_budget=token_budget,
        introstring=introstring,
        dataintro=dataintro,
        nmax=nmax
    )
    messages = [
        {"role": "system", "content": botrole.strip()},
        {"role": "user", "content": msg},
    ]

    # Keep behavior similar to your snippet (chat.completions)
    resp = client.chat.completions.create(
        model=chat_model,
        messages=messages,
        temperature=temperature
    )
    return resp.choices[0].message.content


# --------------------- Workers --------------------- #

class ArticlesLoadWorker(QObject):
    finished = pyqtSignal(object, str)  # (items, summary)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, *, text_dir: str, embedding_dir: str, dedup: bool, max_files: int):
        super().__init__()
        self.text_dir = text_dir
        self.embedding_dir = embedding_dir
        self.dedup = dedup
        self.max_files = max_files
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if not self.text_dir or not os.path.isdir(self.text_dir):
                self.error.emit(f"Error: Text directory not found: {self.text_dir}")
                return
            if not self.embedding_dir or not os.path.isdir(self.embedding_dir):
                self.error.emit(f"Error: Embedding directory not found: {self.embedding_dir}")
                return

            def progress_cb(msg: str):
                if self._cancelled:
                    return
                self.progress.emit(msg)

            items, stats = load_Articles(
                self.text_dir,
                self.embedding_dir,
                dedup=self.dedup,
                max_files=self.max_files,
                progress_cb=progress_cb
            )

            if self._cancelled:
                self.error.emit("Load cancelled.")
                return

            summary = (
                "Articles loaded.\n"
                f"Text files scanned: {stats['text_files_seen']}\n"
                f"Embedding files scanned: {stats['embedding_files_seen']}\n"
                f"Matched pairs loaded: {stats['matched']}\n"
                f"Missing embedding matches: {stats['missing_embedding']}\n"
                f"Parse failures: {stats['failed_parse']}\n"
                f"Duplicates skipped: {stats['duplicates_skipped']}"
            )
            self.finished.emit(items, summary)

        except Exception as e:
            self.error.emit(f"Error: {e}")


class QueryWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(
        self,
        *,
        api_key: str,
        chat_model: str,
        embedding_model: str,
        temperature: float,
        token_budget: int,
        nmax: int,
        botrole: str,
        introstring: str,
        dataintro: str,
        articlequery: str,
        botquery: str,
        items: List[ArticlesItem]
    ):
        super().__init__()
        self.api_key = api_key
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.temperature = temperature
        self.token_budget = token_budget
        self.nmax = nmax
        self.botrole = botrole
        self.introstring = introstring
        self.dataintro = dataintro
        self.articlequery = articlequery
        self.botquery = botquery
        self.items = items

    def run(self):
        try:
            if not self.api_key:
                self.error.emit("Error: Please provide an OpenAI API key.")
                return
            if not self.items:
                self.error.emit("Error: No articles loaded. Click 'Load Articles' first.")
                return
            if not self.botquery.strip():
                self.error.emit("Error: Please enter a question.")
                return
            if not self.articlequery.strip():
                self.error.emit("Error: Please enter a search query (or enable 'Use Question as Search').")
                return

            client = OpenAI(api_key=self.api_key, timeout=60)

            self.progress.emit("Ranking documents by embedding similarity...")
            answer = ask(
                client,
                self.articlequery,
                self.botquery,
                self.items,
                chat_model=self.chat_model,
                embedding_model=self.embedding_model,
                token_budget=self.token_budget,
                botrole=self.botrole,
                introstring=self.introstring,
                dataintro=self.dataintro,
                nmax=self.nmax,
                temperature=self.temperature
            )
            self.finished.emit(answer)

        except Exception as e:
            self.error.emit(f"Error: {e}")


# --------------------- GUI --------------------- #

class EmbeddingChatGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Embedding Articles Chat")
        self.setGeometry(200, 200, 780, 900)

        self._thread = None
        self._worker = None

        self._Articles_items: List[ArticlesItem] = []

        app = QApplication.instance()
        app_font_size = app.font().pointSize() if app is not None else 12

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)

        # Font size
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

        # API key
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

        # Articles selection
        Articles_group = QGroupBox("Articles")
        Articles_layout = QVBoxLayout()

        text_layout = QHBoxLayout()
        text_layout.addWidget(QLabel("Text directory (.txt articles):"))
        self.text_dir_edit = QLineEdit()
        self.text_dir_btn = QPushButton("Browse")
        self.text_dir_btn.clicked.connect(self.browse_text_dir)
        text_layout.addWidget(self.text_dir_edit)
        text_layout.addWidget(self.text_dir_btn)
        Articles_layout.addLayout(text_layout)

        emb_layout = QHBoxLayout()
        emb_layout.addWidget(QLabel("Embedding directory (.txt JSON vectors):"))
        self.emb_dir_edit = QLineEdit()
        self.emb_dir_btn = QPushButton("Browse")
        self.emb_dir_btn.clicked.connect(self.browse_emb_dir)
        emb_layout.addWidget(self.emb_dir_edit)
        emb_layout.addWidget(self.emb_dir_btn)
        Articles_layout.addLayout(emb_layout)

        options_layout = QHBoxLayout()
        self.dedup_checkbox = QCheckBox("Deduplicate (tail-match)")
        self.dedup_checkbox.setChecked(True)
        options_layout.addWidget(self.dedup_checkbox)

        options_layout.addWidget(QLabel("Max files to scan (0 = no limit):"))
        self.max_files_slider = QSlider(Qt.Horizontal)
        self.max_files_slider.setMinimum(0)
        self.max_files_slider.setMaximum(5000)
        self.max_files_slider.setValue(0)
        self.max_files_slider.setTickInterval(500)
        self.max_files_slider.setSingleStep(50)
        self.max_files_slider.valueChanged.connect(self._update_max_files_label)
        options_layout.addWidget(self.max_files_slider)
        self.max_files_value = QLabel("0")
        self.max_files_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        options_layout.addWidget(self.max_files_value)

        Articles_layout.addLayout(options_layout)

        load_row = QHBoxLayout()
        self.load_button = QPushButton("Load Articles")
        self.load_button.clicked.connect(self.load_Articles_clicked)
        self.cancel_load_button = QPushButton("Cancel Load")
        self.cancel_load_button.clicked.connect(self.cancel_clicked)
        self.cancel_load_button.setEnabled(False)
        load_row.addWidget(self.load_button)
        load_row.addWidget(self.cancel_load_button)
        load_row.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        Articles_layout.addLayout(load_row)

        Articles_group.setLayout(Articles_layout)
        main_layout.addWidget(Articles_group)

        # Settings
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout()

        # Chat model
        chat_model_layout = QHBoxLayout()
        chat_model_layout.addWidget(QLabel("Chat Model:"))
        self.chat_model_dropdown = QComboBox()
        # self.chat_model_dropdown.addItems(["gpt-4o", "gpt-4.1", "gpt-5", "gpt-3.5-turbo", "custom-model"])
        self.chat_model_dropdown.addItems(["gpt-5.2", "gpt-5", "gpt-4o", "gpt-3.5-turbo", "custom-model"])
        chat_model_layout.addWidget(self.chat_model_dropdown)
        settings_layout.addLayout(chat_model_layout)

        # Embedding model
        emb_model_layout = QHBoxLayout()
        emb_model_layout.addWidget(QLabel("Embedding Model:"))
        self.emb_model_dropdown = QComboBox()
        self.emb_model_dropdown.addItems(["text-embedding-ada-002", "text-embedding-3-small", "text-embedding-3-large"])
        emb_model_layout.addWidget(self.emb_model_dropdown)

        info_btn = QToolButton()
        info_btn.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        info_btn.setAutoRaise(True)
        info_btn.setToolTip(
            "This tool retrieves the most related texts by cosine similarity of embeddings,\n"
            "then builds a prompt from the top matches within the token budget."
        )
        emb_model_layout.addWidget(info_btn)
        settings_layout.addLayout(emb_model_layout)

        # Max sources
        nmax_layout = QHBoxLayout()
        nmax_layout.addWidget(QLabel("Max retrieved texts (nmax):"))
        self.nmax_slider = QSlider(Qt.Horizontal)
        self.nmax_slider.setMinimum(1)
        self.nmax_slider.setMaximum(50)
        self.nmax_slider.setValue(5)
        self.nmax_slider.setTickInterval(5)
        self.nmax_slider.setSingleStep(1)
        self.nmax_slider.valueChanged.connect(self._update_nmax_label)
        nmax_layout.addWidget(self.nmax_slider)
        self.nmax_value = QLabel("5")
        self.nmax_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        nmax_layout.addWidget(self.nmax_value)
        settings_layout.addLayout(nmax_layout)

        # Token budget
        budget_layout = QHBoxLayout()
        budget_layout.addWidget(QLabel("Token budget:"))
        self.budget_slider = QSlider(Qt.Horizontal)
        self.budget_slider.setMinimum(512)
        self.budget_slider.setMaximum(100000)
        self.budget_slider.setValue(6000)
        self.budget_slider.setTickInterval(2000)
        self.budget_slider.setSingleStep(256)
        self.budget_slider.valueChanged.connect(self._update_budget_label)
        budget_layout.addWidget(self.budget_slider)
        self.budget_value = QLabel(str(self.budget_slider.value()))
        self.budget_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        budget_layout.addWidget(self.budget_value)
        settings_layout.addLayout(budget_layout)

        # Temperature
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Temperature:"))
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setMinimum(0)
        self.temp_slider.setMaximum(10)
        self.temp_slider.setValue(2)
        self.temp_slider.setTickInterval(1)
        self.temp_slider.valueChanged.connect(self._update_temp_label)
        temp_layout.addWidget(self.temp_slider)
        self.temp_value = QLabel("0.2")
        self.temp_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        temp_layout.addWidget(self.temp_value)
        settings_layout.addLayout(temp_layout)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # Advanced prompt & context
        context_group = QGroupBox("Prompt & Context")
        context_layout = QVBoxLayout()

        adv_header = QHBoxLayout()
        self.adv_toggle_btn = QToolButton()
        self.adv_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.adv_toggle_btn.setArrowType(Qt.RightArrow)
        self.adv_toggle_btn.setText("Advanced")
        self.adv_toggle_btn.setCheckable(True)
        self.adv_toggle_btn.setChecked(False)
        self.adv_toggle_btn.clicked.connect(self._toggle_advanced)
        adv_header.addWidget(self.adv_toggle_btn)
        adv_header.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        context_layout.addLayout(adv_header)

        self.advanced_widget = QWidget()
        adv_form_layout = QVBoxLayout(self.advanced_widget)
        adv_form_layout.setContentsMargins(24, 0, 0, 0)

        adv_form_layout.addWidget(QLabel("botrole"))
        self.role_edit = QTextEdit()
        self.role_edit.setPlainText(
            "You are a research assistant. Your job is to answer questions about articles provided to you."
        )
        self.role_edit.setFixedHeight(60)
        adv_form_layout.addWidget(self.role_edit)

        adv_form_layout.addWidget(QLabel("introstring"))
        self.intro_edit = QLineEdit()
        self.intro_edit.setText("Use the articles provided to answer the subsequent question.")
        adv_form_layout.addWidget(self.intro_edit)

        adv_form_layout.addWidget(QLabel("dataintro"))
        self.dataintro_edit = QLineEdit()
        self.dataintro_edit.setText("Here is the next article data section")
        adv_form_layout.addWidget(self.dataintro_edit)

        self.advanced_widget.setVisible(False)
        context_layout.addWidget(self.advanced_widget)

        context_group.setLayout(context_layout)
        main_layout.addWidget(context_group)

        # Query inputs
        main_layout.addWidget(QLabel("Search query (used for embedding similarity):"))
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Enter a search query to retrieve related texts...")
        search_row.addWidget(self.search_edit)
        self.use_question_checkbox = QCheckBox("Use Question as Search")
        self.use_question_checkbox.setChecked(True)
        self.use_question_checkbox.stateChanged.connect(self._sync_search_with_question)
        search_row.addWidget(self.use_question_checkbox)
        main_layout.addLayout(search_row)

        main_layout.addWidget(QLabel("Question (sent to the model):"))
        q_row = QHBoxLayout()
        self.question_edit = QLineEdit()
        self.question_edit.setPlaceholderText("Enter your question and press Ask...")
        self.question_edit.returnPressed.connect(self.ask_clicked)
        q_row.addWidget(self.question_edit)
        self.ask_button = QPushButton("Ask")
        self.ask_button.clicked.connect(self.ask_clicked)
        q_row.addWidget(self.ask_button)
        main_layout.addLayout(q_row)

        # Output
        out_header = QHBoxLayout()
        out_header.addWidget(QLabel("Output"))
        out_header.addItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(self.copy_output_to_clipboard)
        out_header.addWidget(self.copy_button)
        main_layout.addLayout(out_header)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        main_layout.addWidget(self.output_box)

        # Init labels
        self._update_max_files_label(self.max_files_slider.value())
        self._update_nmax_label(self.nmax_slider.value())
        self._update_budget_label(self.budget_slider.value())
        self._update_temp_label(self.temp_slider.value())

        # Adopt current app font
        self.setFont(QApplication.instance().font())

    # -------- UI helpers --------

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

    def _toggle_advanced(self, checked: bool):
        self.advanced_widget.setVisible(checked)
        self.adv_toggle_btn.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def _update_max_files_label(self, value: int):
        self.max_files_value.setText(str(value))

    def _update_nmax_label(self, value: int):
        self.nmax_value.setText(str(value))

    def _update_budget_label(self, value: int):
        self.budget_value.setText(str(value))

    def _update_temp_label(self, slider_val: int):
        self.temp_value.setText(f"{slider_val / 10.0:.1f}")

    def _sync_search_with_question(self):
        if self.use_question_checkbox.isChecked():
            self.search_edit.setEnabled(False)
            self.search_edit.setText(self.question_edit.text().strip())
        else:
            self.search_edit.setEnabled(True)

    def browse_text_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Text Directory")
        if path:
            self.text_dir_edit.setText(path)

    def browse_emb_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Embedding Directory")
        if path:
            self.emb_dir_edit.setText(path)

    def copy_output_to_clipboard(self):
        QApplication.clipboard().setText(self.output_box.toPlainText())
        self.output_box.append("Output copied to clipboard.")

    def _set_busy(self, busy: bool):
        # Basic disable set for safety
        self.setCursor(Qt.BusyCursor if busy else Qt.ArrowCursor)
        self.load_button.setEnabled(not busy)
        self.ask_button.setEnabled(not busy)
        self.cancel_load_button.setEnabled(busy)
        self.question_edit.setEnabled(not busy)
        if not self.use_question_checkbox.isChecked():
            self.search_edit.setEnabled(not busy)
        self.chat_model_dropdown.setEnabled(not busy)
        self.emb_model_dropdown.setEnabled(not busy)
        self.budget_slider.setEnabled(not busy)
        self.nmax_slider.setEnabled(not busy)
        self.temp_slider.setEnabled(not busy)

    def cancel_clicked(self):
        if self._worker and hasattr(self._worker, "cancel"):
            self.output_box.append("Cancel requested...")
            self._worker.cancel()

    # -------- Thread management --------

    def _start_thread(self, worker: QObject, started_fn):
        # Prevent overlapping runs
        if self._thread and self._thread.isRunning():
            self.output_box.append("Another task is still running.")
            return False

        self._worker = worker
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(started_fn)

        # Generic cleanup
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(lambda: setattr(self, "_worker", None))
        self._thread.finished.connect(lambda: setattr(self, "_thread", None))
        return True

    # -------- Articles loading --------

    def load_Articles_clicked(self):
        text_dir = self.text_dir_edit.text().strip()
        emb_dir = self.emb_dir_edit.text().strip()
        dedup = self.dedup_checkbox.isChecked()
        max_files = self.max_files_slider.value()

        worker = ArticlesLoadWorker(text_dir=text_dir, embedding_dir=emb_dir, dedup=dedup, max_files=max_files)

        if not self._start_thread(worker, worker.run):
            return

        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_Articles_loaded)
        worker.error.connect(self._on_error)

        worker.finished.connect(self._thread.quit)
        worker.error.connect(self._thread.quit)

        self._set_busy(True)
        self.output_box.append("Starting articles load...")
        self._thread.start()

    def _on_Articles_loaded(self, items_obj, summary: str):
        self._Articles_items = list(items_obj) if items_obj else []
        self.output_box.append(summary)
        self._set_busy(False)

    # -------- Querying --------

    def ask_clicked(self):
        if self.use_question_checkbox.isChecked():
            self.search_edit.setText(self.question_edit.text().strip())

        api_key = self.api_key_field.text().strip()
        chat_model = self.chat_model_dropdown.currentText().strip()
        emb_model = self.emb_model_dropdown.currentText().strip()
        temperature = self.temp_slider.value() / 10.0 if chat_model == "gpt-4" or chat_model == "gpt-3.5-turbo" else None
        token_budget = self.budget_slider.value()
        nmax = self.nmax_slider.value()

        botrole = self.role_edit.toPlainText().strip()
        introstring = self.intro_edit.text().strip()
        dataintro = self.dataintro_edit.text().strip()

        articlequery = self.search_edit.text().strip()
        botquery = self.question_edit.text().strip()

        worker = QueryWorker(
            api_key=api_key,
            chat_model=chat_model,
            embedding_model=emb_model,
            temperature=temperature,
            token_budget=token_budget,
            nmax=nmax,
            botrole=botrole,
            introstring=introstring,
            dataintro=dataintro,
            articlequery=articlequery,
            botquery=botquery,
            items=self._Articles_items
        )

        if not self._start_thread(worker, worker.run):
            return

        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_answer)
        worker.error.connect(self._on_error)

        worker.finished.connect(self._thread.quit)
        worker.error.connect(self._thread.quit)

        self._set_busy(True)
        self.output_box.append("Submitting query...")
        self._thread.start()

    # -------- Output handlers --------

    def _on_progress(self, msg: str):
        self.output_box.append(msg)

    def _on_answer(self, answer: str):
        chat_model = self.chat_model_dropdown.currentText().strip()
        temperature = self.temp_slider.value() / 10.0
        nmax = self.nmax_slider.value()
        token_budget = self.budget_slider.value()

        self.output_box.append(
            f"\nAnswer (Model={chat_model}, Temp={temperature}, nmax={nmax}, Budget={token_budget}):\n{answer}\n"
        )
        self._set_busy(False)

    def _on_error(self, msg: str):
        self.output_box.append(msg)
        self._set_busy(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if app.font().pointSize() <= 0:
        f = QFont()
        f.setPointSize(12)
        app.setFont(f)

    window = EmbeddingChatGUI()
    window.show()
    sys.exit(app.exec_())
