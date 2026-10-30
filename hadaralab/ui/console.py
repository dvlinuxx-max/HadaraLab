"""Command Window: output log plus a '>>' input line with history."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QVBoxLayout, QWidget)

from .theme import C, code_font_css, code_font_size, set_css, qc, themed




class CommandInput(QLineEdit):
    history_up = Signal()
    history_down = Signal()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Up:
            self.history_up.emit()
            return
        if e.key() == Qt.Key.Key_Down:
            self.history_down.emit()
            return
        super().keyPressEvent(e)


class CommandWindow(QWidget):
    command = Signal(str)

    def set_font_size(self, size):
        set_css(self.log, f"QPlainTextEdit {{ border-radius: 8px; padding: 6px; {code_font_css(size - 1)} }}")
        set_css(self.input, f"QLineEdit {{ {code_font_css(size - 1)} }}")
        set_css(self.prompt, f"color: {C['primary']}; font-weight: 700; {code_font_css(size)}")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.hist_pos = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(20000)
        lay.addWidget(self.log, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.prompt = prompt = QLabel(">>")
        self.input = CommandInput()
        self.input.setPlaceholderText("Type a command    (Up / Down = history)")
        self.input.returnPressed.connect(self._submit)
        self.set_font_size(code_font_size())
        self.input.history_up.connect(lambda: self._walk(-1))
        self.input.history_down.connect(lambda: self._walk(1))
        row.addWidget(prompt)
        row.addWidget(self.input, 1)
        lay.addLayout(row)

        self.fmt_out = QTextCharFormat()
        self.fmt_out.setForeground(qc(C["text"]))
        self.fmt_cmd = QTextCharFormat()
        self.fmt_cmd.setForeground(qc(C["primary_dark"]))
        self.fmt_cmd.setFontWeight(QFont.Weight.Bold)
        self.fmt_err = QTextCharFormat()
        self.fmt_err.setForeground(qc(C["red"]))
        self.fmt_info = QTextCharFormat()
        self.fmt_info.setForeground(qc(C["teal"]))

    def _append(self, text, fmt):
        cur = self.log.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        cur.insertText(text, fmt)
        self.log.setTextCursor(cur)
        self.log.ensureCursorVisible()

    def write(self, text):
        self._append(text, self.fmt_out)

    def write_error(self, text):
        self._append(text if text.endswith("\n") else text + "\n", self.fmt_err)

    def write_info(self, text):
        self._append(text if text.endswith("\n") else text + "\n", self.fmt_info)

    def echo(self, cmd):
        self._append(f">> {cmd}\n", self.fmt_cmd)

    def clear(self):
        self.log.clear()

    def _submit(self):
        text = self.input.text()
        if not text.strip():
            return
        if not self.history or self.history[-1] != text:
            self.history.append(text)
        self.hist_pos = len(self.history)
        self.input.clear()
        self.echo(text)
        self.command.emit(text)

    def _walk(self, step):
        if not self.history:
            return
        self.hist_pos = max(0, min(len(self.history), self.hist_pos + step))
        self.input.setText(self.history[self.hist_pos] if self.hist_pos < len(self.history) else "")

    def set_busy(self, busy):
        self.input.setEnabled(not busy)
        if not busy:
            self.input.setFocus()
