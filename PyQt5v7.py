# Fixed max article selectors into sliders
# Edit 2 - fixed sliders some more
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QComboBox,
    QSlider, QGroupBox, QCheckBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import openai

# --- Chatbot Logic ---
def get_openai_response(
    prompt, model, temperature, api_key,
    botrole, introstring, dataintro, articles_dir,
    max_articles, max_tokens
):
    if not api_key:
        return "Please provide an OpenAI API key."
    # Placeholder response
    return (
        f"[{model} | Temp: {temperature}] Echo: {prompt}\n"
        f"(botrole set, intro used, dataintro noted, dir={articles_dir}, "
        f"max_articles={max_articles}, max_tokens={max_tokens})"
    )

class ChatBotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 Chatbot with OpenAI API Key")
        self.setGeometry(200, 200, 700, 820)

        # Font default
        self.current_font_size = 12
        base_font = QFont()
        base_font.setPointSize(self.current_font_size)
        self.setFont(base_font)

        # Central layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)

        # --- Font Size (descriptor | slider | value) ---
        font_group = QGroupBox("Font")
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font Size:"))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(8, 32)
        self.font_slider.setValue(self.current_font_size)
        self.font_slider.setTickInterval(1)
        self.font_slider.valueChanged.connect(self.change_font_size)
        font_layout.addWidget(self.font_slider)
        self.font_value_label = QLabel(str(self.current_font_size))
        self.font_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        font_layout.addWidget(self.font_value_label)
        font_group.setLayout(font_layout)
        main_layout.addWidget(font_group)

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
        self.model_dropdown.addItems(["gpt-4", "gpt-3.5-turbo", "custom-model"])
        model_layout.addWidget(self.model_dropdown)
        settings_layout.addLayout(model_layout)

        # Max Articles (descriptor | slider | value)
        max_articles_layout = QHBoxLayout()
        max_articles_layout.addWidget(QLabel("Max Articles:"))
        self.max_articles_slider = QSlider(Qt.Horizontal)
        self.max_articles_slider.setMinimum(1)
        self.max_articles_slider.setMaximum(10000)
        self.max_articles_slider.setValue(100)
        self.max_articles_slider.setTickInterval(100)
        self.max_articles_slider.setSingleStep(1)
        self.max_articles_slider.valueChanged.connect(self.update_max_articles_label)
        max_articles_layout.addWidget(self.max_articles_slider)
        self.max_articles_value_label = QLabel("100")
        self.max_articles_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        max_articles_layout.addWidget(self.max_articles_value_label)
        settings_layout.addLayout(max_articles_layout)

        # Max Tokens (descriptor | slider | value) — multiples of 256
        max_tokens_layout = QHBoxLayout()
        max_tokens_layout.addWidget(QLabel("Max Tokens:"))
        self._TOK_STEP = 256
        self.max_tokens_slider = QSlider(Qt.Horizontal)
        self.max_tokens_slider.setMinimum(1)   # 1 * 256 = 256
        self.max_tokens_slider.setMaximum(128000 // self._TOK_STEP)  # 500 steps => 128000
        self.max_tokens_slider.setValue(4096 // self._TOK_STEP)      # 16 => 4096
        self.max_tokens_slider.setTickInterval(4)  # ≈1024 per tick
        self.max_tokens_slider.setSingleStep(1)
        self.max_tokens_slider.valueChanged.connect(self.update_max_tokens_label)
        max_tokens_layout.addWidget(self.max_tokens_slider)
        self.max_tokens_value_label = QLabel("4096")
        self.max_tokens_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        max_tokens_layout.addWidget(self.max_tokens_value_label)
        settings_layout.addLayout(max_tokens_layout)

        # Temperature (descriptor | slider | value)
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

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet(f"font-size: {self.current_font_size}pt;")
        main_layout.addWidget(self.chat_display)

        # Initialize right-side value labels
        self.update_max_articles_label(self.max_articles_slider.value())
        self.update_max_tokens_label(self.max_tokens_slider.value())
        self.update_temp_label()

    # --- Handlers ---
    def change_font_size(self, value: int):
        self.current_font_size = value
        self.font_value_label.setText(str(value))
        f = QFont()
        f.setPointSize(self.current_font_size)
        self.setFont(f)
        self.chat_display.setStyleSheet(f"font-size: {self.current_font_size}pt;")

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

        response = get_openai_response(
            user_input, model, temperature, api_key,
            botrole, introstring, dataintro, articles_dir,
            max_articles, max_tokens
        )

        self.chat_display.append(
            f"Chatbot ({model}, Temp={temperature}, MaxArticles={max_articles}, MaxTokens={max_tokens}):\n{response}\n"
        )
        self.entry.clear()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatBotGUI()
    window.show()
    sys.exit(app.exec_())
