from PySide6.QtWidgets import QCheckBox, QTextEdit, QVBoxLayout, QWidget
from datetime import datetime
from html import escape

class ConsoleWindow(QWidget):
    LOG_COLORS = {
        "INFO": "#9ad1ff",
        "SUCCESS": "#7CFC8A",
        "WARN": "#FFD166",
        "ERROR": "#FF6B6B",
        "DEBUG": "#B9B9FF",
    }

    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout(self)
        self.log_entries = []

        self.show_debug_toggle = QCheckBox("Show DEBUG")
        self.show_debug_toggle.setChecked(False)
        self.show_debug_toggle.toggled.connect(self._refresh_visible_logs)
        self.layout.addWidget(self.show_debug_toggle)

        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)  # Make it read-only for output
        self.layout.addWidget(self.console_output)

        self.log_message("GPS logger console initialized.", level="SUCCESS")

    def _should_display(self, level):
        if level == "DEBUG" and not self.show_debug_toggle.isChecked():
            return False
        return True

    def _format_log_line(self, timestamp, level, message):
        color = self.LOG_COLORS[level]
        safe_message = escape(str(message))
        return (
            f"<span style='color:#8f9bb3'>[{timestamp}]</span> "
            f"<span style='color:{color};font-weight:600'>[{level}]</span> "
            f"<span style='color:#e6edf7'>{safe_message}</span>"
        )

    def _refresh_visible_logs(self):
        self.console_output.clear()
        for timestamp, level, message in self.log_entries:
            if self._should_display(level):
                self.console_output.append(self._format_log_line(timestamp, level, message))
        
    def log_message(self, message, level="INFO"):
        normalized_level = str(level).upper()
        if normalized_level not in self.LOG_COLORS:
            normalized_level = "INFO"

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_entries.append((timestamp, normalized_level, str(message)))

        if self._should_display(normalized_level):
            self.console_output.append(self._format_log_line(timestamp, normalized_level, message))