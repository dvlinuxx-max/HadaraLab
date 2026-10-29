"""Code editor with MATLAB syntax highlighting, line numbers and completion."""

import re

from PySide6.QtCore import QRect, QSize, QStringListModel, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QPainter, QSyntaxHighlighter,
                           QTextCharFormat, QTextCursor, QTextFormat)
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QWidget

from .theme import C, CODE_FONT, set_css, qc, themed
from ..engine.lexer import KEYWORDS


def _fmt(color, bold=False, italic=False):
    f = QTextCharFormat()
    f.setForeground(qc(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class MatlabHighlighter(QSyntaxHighlighter):
    def __init__(self, document, builtin_names):
        super().__init__(document)
        self.f_kw = _fmt("#1565C0", bold=True)
        self.f_builtin = _fmt("#00897B", bold=True)
        self.f_control = _fmt("#D81B60", bold=True)
        self.f_num = _fmt("#EF6C00")
        self.f_str = _fmt("#8E24AA")
        self.f_comment = _fmt("#43A047", italic=True)
        self.f_section = _fmt("#2E7D32", bold=True)
        self.kw_re = re.compile(r"\b(" + "|".join(sorted(KEYWORDS)) + r")\b")
        self.num_re = re.compile(r"(?<![\w.])(\d+\.?\d*([eE][-+]?\d+)?|\.\d+([eE][-+]?\d+)?)[ij]?\b")
        control = {"tf", "zpk", "ss", "step", "impulse", "bode", "margin", "rlocus", "nyquist",
                   "feedback", "series", "parallel", "pid", "routh", "stepinfo", "pzmap",
                   "lsim", "ramp", "damp", "pole", "zero", "dcgain", "minreal", "sgrid",
                   "krange", "ess", "rlocinfo"}
        self.control = control
        self.builtins = set(builtin_names) - control
        self.word_re = re.compile(r"\b[A-Za-z_]\w*\b")

    def highlightBlock(self, text):
        stripped = text.lstrip()
        if stripped.startswith("%%"):
            self.setFormat(0, len(text), self.f_section)
            return
        # find comment start (outside strings)
        comment_at = None
        strings = []
        i = 0
        prev_value = False
        while i < len(text):
            c = text[i]
            if c == "%":
                comment_at = i
                break
            if c == '"' or (c == "'" and not prev_value):
                j = i + 1
                while j < len(text):
                    if text[j] == c:
                        if j + 1 < len(text) and text[j + 1] == c:
                            j += 2
                            continue
                        break
                    j += 1
                strings.append((i, j + 1))
                i = j + 1
                prev_value = True
                continue
            prev_value = c.isalnum() or c in "_)]}'."
            i += 1
        code = text if comment_at is None else text[:comment_at]

        def in_string(pos):
            return any(a <= pos < b for a, b in strings)

        for m in self.num_re.finditer(code):
            if not in_string(m.start()):
                self.setFormat(m.start(), m.end() - m.start(), self.f_num)
        for m in self.word_re.finditer(code):
            if in_string(m.start()):
                continue
            w = m.group()
            if w in KEYWORDS:
                self.setFormat(m.start(), len(w), self.f_kw)
            elif w in self.control:
                self.setFormat(m.start(), len(w), self.f_control)
            elif w in self.builtins:
                self.setFormat(m.start(), len(w), self.f_builtin)
        for a, b in strings:
            self.setFormat(a, b - a, self.f_str)
        if comment_at is not None:
            self.setFormat(comment_at, len(text) - comment_at, self.f_comment)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    run_selection = Signal(str)
    modified_changed = Signal(bool)

    def __init__(self, builtin_names=(), parent=None):
        super().__init__(parent)
        font = QFont()
        font.setFamilies([f.strip() for f in CODE_FONT.split(",")])
        font.setPointSize(11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        set_css(self, "QPlainTextEdit { border: none; border-radius: 0; padding-left: 4px; }")
        self.error_line = None
        self.highlighter = MatlabHighlighter(self.document(), builtin_names)
        self.numbers = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._update_numbers)
        self.cursorPositionChanged.connect(self._highlight_current)
        self.document().modificationChanged.connect(self.modified_changed)
        self._update_margin()
        self._highlight_current()

        words = sorted(set(builtin_names) | KEYWORDS)
        self.completer = QCompleter(self)
        self.completer.setModel(QStringListModel(words, self.completer))
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setWidget(self)
        self.completer.activated.connect(self._insert_completion)
        set_css(self.completer.popup(), 
            f"QListView {{ background: white; border: 1px solid {C['border']}; border-radius: 6px;"
            f" font-family: Consolas; font-size: 10pt; }}"
            f"QListView::item:selected {{ background: {C['select']}; color: {C['text']}; }}")

    # -- line numbers --------------------------------------------------------
    def line_number_width(self):
        digits = max(3, len(str(self.blockCount())))
        return 18 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self, *_):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_numbers(self, rect, dy):
        if dy:
            self.numbers.scroll(0, dy)
        else:
            self.numbers.update(0, rect.y(), self.numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.numbers.setGeometry(QRect(cr.left(), cr.top(), self.line_number_width(), cr.height()))

    def paint_line_numbers(self, event):
        painter = QPainter(self.numbers)
        painter.fillRect(event.rect(), qc("#F5F9FE"))
        painter.setPen(qc(C["border"]))
        painter.drawLine(self.numbers.width() - 1, event.rect().top(),
                         self.numbers.width() - 1, event.rect().bottom())
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if self.error_line is not None and number + 1 == self.error_line:
                    painter.fillRect(0, top, self.numbers.width() - 1, bottom - top, qc("#FFE3E8"))
                    painter.setPen(qc(C["red"]))
                elif number == current:
                    painter.setPen(qc(C["primary"]))
                else:
                    painter.setPen(qc("#9AAAC0"))
                painter.drawText(0, top, self.numbers.width() - 8, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1

    def _highlight_current(self):
        sels = []
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(qc(C["current_line"]))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        sels.append(sel)
        if self.error_line is not None:
            block = self.document().findBlockByNumber(self.error_line - 1)
            if block.isValid():
                err = QTextEdit.ExtraSelection()
                err.format.setBackground(qc("#FFF0F3"))
                err.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                err.cursor = QTextCursor(block)
                sels.append(err)
        self.setExtraSelections(sels)

    def set_error_line(self, line):
        self.error_line = line
        self._highlight_current()
        self.numbers.update()
        if line:
            block = self.document().findBlockByNumber(line - 1)
            if block.isValid():
                cur = QTextCursor(block)
                self.setTextCursor(cur)
                self.centerCursor()

    # -- editing helpers -----------------------------------------------------
    def _word_under_cursor(self):
        cur = self.textCursor()
        cur.select(QTextCursor.SelectionType.WordUnderCursor)
        return cur.selectedText()

    def _insert_completion(self, text):
        cur = self.textCursor()
        prefix = self.completer.completionPrefix()
        cur.insertText(text[len(prefix):])
        self.setTextCursor(cur)

    def keyPressEvent(self, e):
        popup = self.completer.popup()
        if popup.isVisible() and e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return,
                                              Qt.Key.Key_Tab, Qt.Key.Key_Escape):
            e.ignore()
            return
        if self.error_line is not None and e.text():
            self.set_error_line(None)
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._newline_with_indent()
            return
        if e.key() == Qt.Key.Key_Tab and not e.modifiers():
            self.textCursor().insertText("    ")
            return
        if e.key() == Qt.Key.Key_Backtab:
            self._indent(-1)
            return
        if e.key() == Qt.Key.Key_Slash and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.toggle_comment()
            return
        if e.key() == Qt.Key.Key_F9:
            text = self.textCursor().selectedText().replace(" ", "\n")
            if not text:
                text = self.textCursor().block().text()
            self.run_selection.emit(text)
            return
        super().keyPressEvent(e)
        self._maybe_complete(e)

    def _maybe_complete(self, e):
        word = self._word_under_cursor()
        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.StartOfWord, QTextCursor.MoveMode.KeepAnchor)
        prefix = cur.selectedText()
        if len(prefix) < 2 or not e.text() or not (e.text().isalnum() or e.text() == "_"):
            self.completer.popup().hide()
            return
        if prefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(prefix)
            self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))
        if self.completer.completionCount() == 0 or (
                self.completer.completionCount() == 1 and self.completer.currentCompletion() == word):
            self.completer.popup().hide()
            return
        rect = self.cursorRect()
        rect.setWidth(self.completer.popup().sizeHintForColumn(0) +
                      self.completer.popup().verticalScrollBar().sizeHint().width() + 20)
        self.completer.complete(rect)

    def _newline_with_indent(self):
        cur = self.textCursor()
        line = cur.block().text()
        indent = re.match(r"\s*", line).group()
        first = line.strip().split("%")[0].strip()
        word = re.match(r"[A-Za-z]+", first)
        word = word.group() if word else ""
        if word in ("if", "for", "while", "switch", "function", "else", "elseif", "case", "otherwise") \
                and not re.search(r"\bend\b\s*;?\s*$", first):
            indent += "    "
        cur.insertText("\n" + indent)
        self.setTextCursor(cur)

    def _indent(self, direction):
        cur = self.textCursor()
        start, end = cur.selectionStart(), cur.selectionEnd()
        cur.setPosition(start)
        first = cur.blockNumber()
        cur.setPosition(end)
        last = cur.blockNumber()
        cur.beginEditBlock()
        for n in range(first, last + 1):
            block = self.document().findBlockByNumber(n)
            c = QTextCursor(block)
            if direction > 0:
                c.insertText("    ")
            else:
                text = block.text()
                k = len(text) - len(text.lstrip(" "))
                for _ in range(min(4, k)):
                    c.deleteChar()
        cur.endEditBlock()

    def toggle_comment(self):
        cur = self.textCursor()
        start, end = cur.selectionStart(), cur.selectionEnd()
        cur.setPosition(start)
        first = cur.blockNumber()
        cur.setPosition(end)
        last = cur.blockNumber()
        blocks = [self.document().findBlockByNumber(n) for n in range(first, last + 1)]
        all_commented = all(b.text().lstrip().startswith("%") or not b.text().strip() for b in blocks)
        cur.beginEditBlock()
        for b in blocks:
            text = b.text()
            if not text.strip():
                continue
            c = QTextCursor(b)
            k = len(text) - len(text.lstrip())
            c.movePosition(QTextCursor.MoveOperation.Right, n=k)
            if all_commented:
                c.deleteChar()
                if c.block().text()[k:k + 1] == " ":
                    c.deleteChar()
            else:
                c.insertText("% ")
        cur.endEditBlock()
