# PyQtChat.py
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QComboBox,
    QSlider, QGroupBox, QCheckBox, QFileDialog
)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QFont
import openai  # kept if you plan to use it later
from openai import OpenAI
import os.path

def create_file(client, file_path):
    # Handle local file path
    with open(file_path, "rb") as file_content:
        result = client.files.create(
            file=file_content,
            purpose="assistants"
            )
    # print(result.id)
    return result.id

class ChatBotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 Chatbot with OpenAI API Key")
        self.setGeometry(200, 200, 700, 820)
        self.client = None

        # --- Initialize to current *global* font size ---
        app = QApplication.instance()
        app_font_size = app.font().pointSize() if app is not None else 12

        # Central layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)

        # --- Font Size (descriptor | slider | value) ---
        # font_group = QGroupBox("Font")
        # font_layout = QHBoxLayout()
        # font_layout.addWidget(QLabel("Font Size:"))
        # self.font_slider = QSlider(Qt.Horizontal)
        # self.font_slider.setRange(8, 32)
        # self.font_slider.setValue(app_font_size)
        # self.font_slider.setTickInterval(1)
        # self.font_slider.valueChanged.connect(self.change_font_size)
        # font_layout.addWidget(self.font_slider)
        # self.font_value_label = QLabel(str(app_font_size))
        # self.font_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # font_layout.addWidget(self.font_value_label)
        # font_group.setLayout(font_layout)
        # main_layout.addWidget(font_group)

        # Attempt to fix global font thing which failed
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
        self.model_dropdown.addItems(["gpt-5", "gpt-4", "gpt-3.5-turbo", "custom-model"])
        model_layout.addWidget(self.model_dropdown)
        settings_layout.addLayout(model_layout)

        # Max Articles
        max_articles_layout = QHBoxLayout()
        max_articles_layout.addWidget(QLabel("Max Articles:"))
        self.max_articles_slider = QSlider(Qt.Horizontal)
        self.max_articles_slider.setMinimum(0)
        self.max_articles_slider.setMaximum(100)
        self.max_articles_slider.setValue(10)
        self.max_articles_slider.setTickInterval(100)
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
        self.max_tokens_slider.setMaximum(50000 // self._TOK_STEP)
        self.max_tokens_slider.setValue(4096 // self._TOK_STEP)      # 16 => 4096
        self.max_tokens_slider.setTickInterval(4)  # ≈1024 per tick
        self.max_tokens_slider.setSingleStep(1)
        self.max_tokens_slider.valueChanged.connect(self.update_max_tokens_label)
        max_tokens_layout.addWidget(self.max_tokens_slider)
        self.max_tokens_value_label = QLabel("4096")
        self.max_tokens_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        max_tokens_layout.addWidget(self.max_tokens_value_label)
        settings_layout.addLayout(max_tokens_layout)

        # Temperature
        temp_layout = QHBoxLayout()
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

        # botrole
        context_layout.addWidget(QLabel("botrole"))
        self.role_edit = QTextEdit()
        self.role_edit.setPlainText(
            "You are a research assistant. Your job is to answer questions about articles provided to you."
        )
        self.role_edit.setFixedHeight(60)
        context_layout.addWidget(self.role_edit)

        # introstring
        context_layout.addWidget(QLabel("introstring"))
        self.intro_edit = QLineEdit()
        self.intro_edit.setText("Use the articles provided to answer the subsequent question.")
        context_layout.addWidget(self.intro_edit)

        # dataintro
        context_layout.addWidget(QLabel("dataintro"))
        self.dataintro_edit = QLineEdit()
        self.dataintro_edit.setText("Here is the next article data section")
        context_layout.addWidget(self.dataintro_edit)

        context_group.setLayout(context_layout)
        main_layout.addWidget(context_group)

        # --- Prompt label + input ---
        main_layout.addWidget(QLabel("Chatbot Prompt: Type your question for the assistant and press Enter or click Send."))

        input_layout = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Type your message…")
        self.entry.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.entry)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)
        main_layout.addLayout(input_layout)

        # Chat display (inherits app/window font; no stylesheet needed)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        main_layout.addWidget(self.chat_display)

        # Initialize right-side value labels
        self.update_max_articles_label(self.max_articles_slider.value())
        self.update_max_tokens_label(self.max_tokens_slider.value())
        self.update_temp_label()

        # Ensure our own widgets adopt the current app font immediately
        # (helpful if this window is launched standalone).
        self.setFont(QApplication.instance().font())

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

    # --- Handlers ---
    def change_font_size(self, value: int):
        # This updates the *global* application font so all windows reflect the change.
        self.font_value_label.setText(str(value))
        f = QFont()
        f.setPointSize(value)
        QApplication.instance().setFont(f)
        # Optional: ensure immediate update for this window if needed.
        self.setFont(f)

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

    def send_message(self):
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
        #print(articles_dir)

        # Add additional article functionality here:

        response = self.get_openai_response(
            user_input, model, temperature, api_key,
            botrole, introstring, dataintro, articles_dir,
            max_articles, max_tokens
        )

        self.chat_display.append(
            f"Chatbot ({model}, Temp={temperature}, MaxArticles={max_articles}, MaxTokens={max_tokens}):\n{response}\n"
        )


        self.entry.clear()

    # --- Chatbot Logic (unchanged placeholder) ---
    def get_openai_response(self,
            prompt, model, temperature, api_key,
            botrole, introstring, dataintro, articles_dir,
            max_articles, max_tokens
    ):
        if not api_key:
            return "Error: Please provide an OpenAI API key."

        if not articles_dir:
            return "Error: Please provide a file path for article pdfs to search"
        #print(articles_dir)

        # Prompting Chatbot
        if self.client == None:
            self.client = OpenAI(api_key=api_key)

        #NEW FILE SEARCH PROMPTING
        # print(articles_dir)
        # print(filepath for filepath in articles_dir)
        #return
        articlepathlist = [os.path.join(articles_dir, name) for name in os.listdir(articles_dir) if name.endswith(".pdf")]
        file_id_list = [create_file(self.client, filepath) for filepath in articlepathlist]

        vector_store = self.client.vector_stores.create(
            name="knowledge_base"
        )

        for id in file_id_list:
            self.client.vector_stores.files.create(
                vector_store_id=vector_store.id,
                file_id=id
            )

        # Check Status: Run this code until the file is ready to be used (i.e., when the status is completed).
        # print(f"Analyzing files")
        self.chat_display.append(f"Analyzing files")

        result = self.client.vector_stores.files.list(
            vector_store_id=vector_store.id
        )

        # print(f"Querying Model")
        self.chat_display.append(f"Querying Model")

        response = self.client.responses.create(
            model=model,
            input=prompt,
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store.id]
            }],
            include=["file_search_call.results"]
        )
        response_message = response.output_text

        return response_message

        # print(response)


        # OLD BASIC PROMPTING
        # response = self.client.responses.create(
        #     model=model,
        #     input=prompt,
        #     # tools=[{
        #     #     "type": "file_search",
        #     #     "vector_store_ids": [vector_store.id]
        #     # }],
        #     # include=["file_search_call.results"]
        # )



        #     (
        #     f"[{model} | Temp: {temperature}] Echo: {prompt}\n"
        #     f"(botrole set, intro used, dataintro noted, dir={articles_dir}, "
        #     f"max_articles={max_articles}, max_tokens={max_tokens})"
        # )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # If launched standalone, set a sensible default font globally:
    if app.font().pointSize() <= 0:
        f = QFont()
        f.setPointSize(12)
        app.setFont(f)
    window = ChatBotGUI()
    window.show()
    sys.exit(app.exec_())
