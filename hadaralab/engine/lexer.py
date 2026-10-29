"""Lexer for the HadaraLab MATLAB-like language.

Converts source text into a flat list of tokens. Handles the MATLAB quirks
that a plain tokenizer gets wrong:
  * ' is a transpose after a value, otherwise it starts a string
  * inside [ ] whitespace separates elements: [1 -2] has two elements,
    [1 - 2] has one
  * inside [ ] a newline starts a new row
  * command syntax:  hold on  ->  hold('on')
"""

from dataclasses import dataclass

from .errors import MatlabError

KEYWORDS = {
    "if", "elseif", "else", "end", "for", "while", "break", "continue",
    "function", "return", "switch", "case", "otherwise", "do", "until",
}

# Words that accept MATLAB "command syntax" (e.g. `grid on`, `close all`).
COMMAND_WORDS = {
    "hold", "grid", "clc", "clear", "close", "format", "clf", "figure",
    "axis", "more", "warning", "box", "clearvars", "disp", "help", "legend",
    "minor",
}

THREE_CHAR_OPS = {"..."}
TWO_CHAR_OPS = {
    "==", "~=", "!=", "<=", ">=", "&&", "||", ".*", "./", ".\\", ".^", ".'",
}
ONE_CHAR_OPS = set("+-*/\\^<>=&|~!:,;()[]{}.@")


@dataclass
class Token:
    kind: str     # NUM, STR, IDENT, KW, OP, NL, EOF, CMDARGS
    value: object
    line: int
    col: int
    space_before: bool = False

    def __repr__(self):
        return f"Token({self.kind},{self.value!r},L{self.line})"


def _is_ident_start(c):
    return c.isalpha() or c == "_"


def _is_ident_char(c):
    return c.isalnum() or c == "_"


class Lexer:
    def __init__(self, src):
        self.src = src.replace("\r\n", "\n").replace("\r", "\n")
        self.i = 0
        self.line = 1
        self.col = 1
        self.tokens = []
        # Stack of open brackets: '[', '{' or '('
        self.stack = []

    # -- helpers -----------------------------------------------------------
    def peek(self, k=0):
        # "\0" (not "") past the end, so tests like  peek() in "ij"  stay False
        j = self.i + k
        return self.src[j] if j < len(self.src) else "\0"

    def advance(self, n=1):
        for _ in range(n):
            if self.i < len(self.src):
                if self.src[self.i] == "\n":
                    self.line += 1
                    self.col = 1
                else:
                    self.col += 1
                self.i += 1

    def in_matrix(self):
        return bool(self.stack) and self.stack[-1] in "[{"

    def prev(self):
        return self.tokens[-1] if self.tokens else None

    def prev_is_value_end(self):
        """True when the previous token ends a value (so ' is transpose)."""
        p = self.prev()
        if p is None:
            return False
        if p.kind in ("NUM", "IDENT", "STR"):
            return True
        if p.kind == "KW" and p.value == "end" and self.stack:
            return True
        if p.kind == "OP" and p.value in (")", "]", "}", "'", ".'"):
            return True
        return False

    def at_statement_start(self):
        p = self.prev()
        return p is None or p.kind == "NL" or (
            p.kind == "OP" and p.value in (";", ",") and not self.stack)

    def add(self, kind, value, line, col, space):
        self.tokens.append(Token(kind, value, line, col, space))

    def error(self, msg):
        raise MatlabError(msg, self.line)

    # -- main loop ---------------------------------------------------------
    def tokenize(self):
        space = False
        while self.i < len(self.src):
            c = self.peek()
            line, col = self.line, self.col

            # Block comments %{ ... %}
            if c == "%" and self.peek(1) == "{" and self._line_is_only("%{"):
                self._skip_block_comment()
                continue

            if c in "%#" and not (c == "#" and self.in_matrix()):
                while self.i < len(self.src) and self.peek() != "\n":
                    self.advance()
                continue

            # Line continuation
            if self.src.startswith("...", self.i):
                while self.i < len(self.src) and self.peek() != "\n":
                    self.advance()
                self.advance()  # the newline
                space = True
                continue

            if c in " \t":
                self.advance()
                space = True
                continue

            if c == "\n":
                self.advance()
                if self.in_matrix():
                    # newline inside [ ] separates rows
                    p = self.prev()
                    if p and not (p.kind == "OP" and p.value in (";", "[", "{", ",")):
                        self.add("OP", ";", line, col, space)
                elif self.stack:
                    pass  # newline inside ( ) is ignored
                else:
                    self.add("NL", "\n", line, col, space)
                space = False
                continue

            # Inside a matrix, whitespace between two terms acts as a comma
            if self.in_matrix() and space and self._matrix_needs_comma(c):
                self.add("OP", ",", line, col, True)

            # Command syntax: `hold on`, `close all`, `format long`
            if _is_ident_start(c) and self.at_statement_start() and not self.stack:
                if self._try_command_syntax(line, col, space):
                    space = False
                    continue

            if c.isdigit() or (c == "." and self.peek(1).isdigit()):
                self._number(line, col, space)
            elif _is_ident_start(c):
                self._ident(line, col, space)
            elif c == '"':
                self._string('"', line, col, space)
            elif c == "'":
                if self.prev_is_value_end() and not (space and self.in_matrix()):
                    self.advance()
                    self.add("OP", "'", line, col, space)
                else:
                    self._string("'", line, col, space)
            else:
                self._operator(line, col, space)
            space = False

        if self.stack:
            self.error(f"Unbalanced '{self.stack[-1]}' at end of input.")
        self.add("NL", "\n", self.line, self.col, False)
        self.add("EOF", None, self.line, self.col, False)
        return self.tokens

    def _line_is_only(self, marker):
        start = self.src.rfind("\n", 0, self.i) + 1
        end = self.src.find("\n", self.i)
        end = len(self.src) if end == -1 else end
        return self.src[start:end].strip() == marker

    def _skip_block_comment(self):
        depth = 0
        while self.i < len(self.src):
            start = self.i
            end = self.src.find("\n", start)
            end = len(self.src) if end == -1 else end
            text = self.src[start:end].strip()
            if text == "%{":
                depth += 1
            elif text == "%}":
                depth -= 1
            while self.i < end:
                self.advance()
            self.advance()
            if depth == 0:
                return

    def _matrix_needs_comma(self, c):
        p = self.prev()
        if p is None:
            return False
        prev_ends_term = p.kind in ("NUM", "IDENT", "STR") or (
            p.kind == "OP" and p.value in (")", "]", "}", "'", ".'")) or (
            p.kind == "KW" and p.value == "end")
        if not prev_ends_term:
            return False
        nxt = self.peek(1)
        if c in "+-":
            # [a -b] -> two elements ; [a - b] / [a -= b] -> binary
            return nxt not in " \t\n" and nxt != "="
        if c == "'" or c == '"':
            return True
        if c in "([{@~!":
            if c == "~" and nxt == "=":
                return False
            if c == "!" and nxt == "=":
                return False
            return True
        if c.isalnum() or c == "_" or (c == "." and nxt.isdigit()):
            return True
        return False

    def _try_command_syntax(self, line, col, space):
        j = self.i
        while j < len(self.src) and _is_ident_char(self.src[j]):
            j += 1
        word = self.src[self.i:j]
        if word not in COMMAND_WORDS:
            return False
        k = j
        if k >= len(self.src) or self.src[k] not in " \t":
            return False
        while k < len(self.src) and self.src[k] in " \t":
            k += 1
        if k >= len(self.src):
            return False
        ch = self.src[k]
        nxt = self.src[k + 1] if k + 1 < len(self.src) else ""
        # Not command syntax if it looks like an expression: x = 1, x (1), x + 1
        if ch in "=(" or (ch in "+-*/^<>&|~" and nxt in " \t=") or ch in "\n;,%":
            return False
        if not (_is_ident_start(ch) or ch.isdigit() or ch in "-'"):
            return False
        # Collect the rest of the line up to ; , % or newline
        end = k
        while end < len(self.src) and self.src[end] not in "\n;,%":
            end += 1
        rest = self.src[k:end].strip()
        args = [a.strip("'") for a in rest.split()]
        self.add("IDENT", word, line, col, space)
        self.add("CMDARGS", args, line, col, True)
        while self.i < end:
            self.advance()
        return True

    def _number(self, line, col, space):
        start = self.i
        while self.peek().isdigit():
            self.advance()
        if self.peek() == "." and not self.src.startswith(".*", self.i) \
                and not self.src.startswith("./", self.i) \
                and not self.src.startswith(".^", self.i) \
                and not self.src.startswith(".\\", self.i) \
                and not self.src.startswith(".'", self.i):
            self.advance()
            while self.peek().isdigit():
                self.advance()
        if self.peek() in "eEdD" and (self.peek(1).isdigit() or (
                self.peek(1) in "+-" and self.peek(2).isdigit())):
            self.advance()
            if self.peek() in "+-":
                self.advance()
            while self.peek().isdigit():
                self.advance()
        text = self.src[start:self.i].replace("d", "e").replace("D", "e")
        value = float(text)
        # Imaginary literal: 3i, 2.5j
        if self.peek() in "ij" and not _is_ident_char(self.peek(1)):
            self.advance()
            value = complex(0, value)
        self.add("NUM", value, line, col, space)

    def _ident(self, line, col, space):
        start = self.i
        while _is_ident_char(self.peek()):
            self.advance()
        word = self.src[start:self.i]
        if word in KEYWORDS:
            # `end` inside an index means "last element"
            self.add("KW", word, line, col, space)
        else:
            self.add("IDENT", word, line, col, space)

    def _string(self, quote, line, col, space):
        self.advance()
        out = []
        while True:
            c = self.peek()
            if c == "\0" or c == "\n":
                self.error("String is not terminated properly.")
            if c == quote:
                if self.peek(1) == quote:
                    out.append(quote)
                    self.advance(2)
                    continue
                self.advance()
                break
            out.append(c)
            self.advance()
        self.add("STR", "".join(out), line, col, space)

    def _operator(self, line, col, space):
        two = self.src[self.i:self.i + 2]
        c = self.peek()
        if two in TWO_CHAR_OPS:
            raw = two
        elif c in ONE_CHAR_OPS:
            raw = c
        else:
            self.error(f"Invalid character '{c}' in expression.")
        self.advance(len(raw))
        op = {"!=": "~=", "!": "~"}.get(raw, raw)
        if op in ("(", "[", "{"):
            self.stack.append(op)
        elif op in (")", "]", "}"):
            match = {")": "(", "]": "[", "}": "{"}[op]
            if not self.stack or self.stack[-1] != match:
                self.error(f"Unbalanced or unexpected '{op}'.")
            self.stack.pop()
        self.add("OP", op, line, col, space)


def tokenize(src):
    return Lexer(src).tokenize()
