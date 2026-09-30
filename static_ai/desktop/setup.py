"""Native first-run mode selection and credential entry."""

import os

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..config import Model


class SetupDialog(QDialog):
    def __init__(self, config, credentials, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose your AI · Static")
        self.setMinimumWidth(500)
        self.config, self.credentials = config, credentials
        self.selected_model = None
        self.secret = ""
        layout = QVBoxLayout(self)
        title = QLabel("A little less to do.")
        title.setObjectName("title")
        layout.addWidget(title)
        copy = QLabel(
            "Choose what powers Static. You can change this later from AI setup in the app menu. Python is already included in the Windows download."
        )
        copy.setWordWrap(True)
        layout.addWidget(copy)
        self.mode = QComboBox()
        self.mode.addItem("API key · a cloud provider", "api")
        self.mode.addItem("Ollama · AI on this computer", "ollama")
        self.mode.addItem("Another local server · e.g. LM Studio", "other")
        layout.addWidget(self.mode)
        self.local_copy = QLabel(
            "Ollama runs models on your PC. Static starts it when needed and asks before installing it or downloading models. You can decline and set it up later."
        )
        self.local_copy.setWordWrap(True)
        layout.addWidget(self.local_copy)
        self.form = QFormLayout()
        self.name = QLineEdit("My API model")
        self.endpoint = QLineEdit("https://api.openai.com/v1")
        self.model = QLineEdit()
        self.model.setPlaceholderText("Exact model ID from your provider")
        self.key_name = QLineEdit("STATIC_DESKTOP_API_KEY")
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Stored in Windows Credential Manager")
        self.input_price, self.output_price = QDoubleSpinBox(), QDoubleSpinBox()
        for spin in (self.input_price, self.output_price):
            spin.setDecimals(4)
            spin.setRange(0, 10000)
            spin.setSuffix(" USD / 1M tokens")
        self.confirm = QCheckBox("I verified these prices with my provider (0 means free).")
        self.token_parameter = QComboBox()
        self.token_parameter.addItem("max_tokens", "max_tokens")
        self.token_parameter.addItem("max_completion_tokens", "max_completion_tokens")
        for label, widget in (
            ("Connection name", self.name),
            ("API base URL", self.endpoint),
            ("Model ID", self.model),
            ("Key variable name", self.key_name),
            ("API key", self.key),
            ("Input price", self.input_price),
            ("Output price", self.output_price),
            ("Output token field", self.token_parameter),
        ):
            self.form.addRow(label, widget)
        layout.addLayout(self.form)
        layout.addWidget(self.confirm)
        copy = QLabel(
            "Use a model with tool calling. API usage is charged by your provider; Static uses your saved budgets. This selects one chat model; advanced routing and media models are in Connections."
        )
        copy.setWordWrap(True)
        layout.addWidget(copy)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.mode.currentIndexChanged.connect(self.change_mode)
        current = config.settings.models[0]
        if current.local:
            self.mode.setCurrentIndex(1 if ":11434" in current.base_url else 2)
        self.change_mode()
        self.name.setText(current.name)
        self.endpoint.setText(current.base_url)
        self.model.setText(current.model)
        if current.key_env:
            self.key_name.setText(current.key_env)
        self.input_price.setValue(current.input_per_million)
        self.output_price.setValue(current.output_per_million)
        self.confirm.setChecked(current.pricing_confirmed)
        self.token_parameter.setCurrentIndex(self.token_parameter.findData(current.token_parameter))

    def change_mode(self):
        mode = self.mode.currentData()
        cloud = mode == "api"
        for widget in (self.key_name, self.key, self.input_price, self.output_price):
            widget.setVisible(cloud)
            self.form.labelForField(widget).setVisible(cloud)
        self.confirm.setVisible(cloud)
        self.local_copy.setVisible(mode == "ollama")
        if mode == "ollama":
            self.name.setText("Ollama · Qwen 3")
            self.endpoint.setText("http://localhost:11434/v1")
            self.model.setText("qwen3:4b")
        elif mode == "other":
            self.name.setText("My local model")
            self.endpoint.setText("http://localhost:1234/v1")
            self.model.clear()
        else:
            self.name.setText("My API model")
            self.endpoint.setText("https://api.openai.com/v1")
            self.model.clear()

    def accept(self):
        try:
            cloud = self.mode.currentData() == "api"
            self.selected_model = Model(
                id="desktop",
                name=self.name.text().strip(),
                model=self.model.text().strip(),
                base_url=self.endpoint.text().strip(),
                local=not cloud,
                key_env=self.key_name.text().strip() if cloud else "",
                input_per_million=self.input_price.value() if cloud else 0,
                output_per_million=self.output_price.value() if cloud else 0,
                pricing_confirmed=self.confirm.isChecked() if cloud else False,
                token_parameter=self.token_parameter.currentData(),
            )
            self.secret = self.key.text().strip() if cloud else ""
            if cloud:
                self.credentials.target(self.selected_model.key_env)
                existing = os.getenv(self.selected_model.key_env) or self.credentials.get(
                    self.selected_model.key_env
                )
                if not self.secret and not existing:
                    raise ValueError("Enter your provider API key.")
            super().accept()
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Check your connection", str(exc))


class KeysDialog(QDialog):
    def __init__(self, config, credentials, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API keys · Static")
        self.setMinimumSize(510, 380)
        self.credentials = credentials
        layout = QVBoxLayout(self)
        copy = QLabel(
            "Saved in Windows Credential Manager. Leave a field blank to keep its key, or select Remove to delete it. Configure provider models in Connections."
        )
        copy.setWordWrap(True)
        layout.addWidget(copy)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        fields = QVBoxLayout(content)
        self.rows = []
        names = sorted(
            {
                "BRAVE_API_KEY",
                "REPLICATE_API_TOKEN",
                *[m.key_env for m in config.settings.models if m.key_env],
            }
        )
        for name in names:
            fields.addWidget(QLabel(name + (" · available" if os.getenv(name) else " · not set")))
            secret = QLineEdit()
            secret.setEchoMode(QLineEdit.EchoMode.Password)
            secret.setPlaceholderText("New key (optional)")
            remove = QCheckBox("Remove this key")
            fields.addWidget(secret)
            fields.addWidget(remove)
            self.rows.append((name, secret, remove))
        scroll.setWidget(content)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        try:
            for name, secret, remove in self.rows:
                if remove.isChecked():
                    self.credentials.delete(name)
                elif secret.text().strip():
                    self.credentials.save(name, secret.text().strip())
            super().accept()
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Could not save keys", str(exc))
