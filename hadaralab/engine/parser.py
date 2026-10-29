"""Recursive-descent parser: tokens -> AST.

Operator precedence follows MATLAB (lowest to highest):
    ||   &&   |   &   comparisons   :   + -   * / \\ .* ./ .\\
    unary + - ~   ^ .^ (left associative)   postfix ' .' () {} .field
"""

from . import ast as A
from .errors import MatlabError
from .lexer import tokenize

BLOCK_END = {"end", "else", "elseif", "case", "otherwise", "function"}
CMP_OPS = {"==", "~=", "<", "<=", ">", ">="}
MUL_OPS = {"*", "/", "\\", ".*", "./", ".\\"}


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.p = 0
        self.index_depth = 0   # >0 while parsing inside an index -> `end` allowed
        self.matrix_depth = 0

    # -- token helpers -------------------------------------------------------
    @property
    def tok(self):
        return self.toks[self.p]

    def peek(self, k=1):
        j = min(self.p + k, len(self.toks) - 1)
        return self.toks[j]

    def next(self):
        t = self.toks[self.p]
        self.p += 1
        return t

    def is_op(self, *ops):
        t = self.tok
        return t.kind == "OP" and t.value in ops

    def is_kw(self, *kws):
        t = self.tok
        return t.kind == "KW" and t.value in kws

    def expect_op(self, op):
        if not self.is_op(op):
            self.error(f"Expected '{op}' but found {self.describe(self.tok)}.")
        return self.next()

    def expect_kw(self, kw):
        if not self.is_kw(kw):
            self.error(f"Expected '{kw}' but found {self.describe(self.tok)}.")
        return self.next()

    def describe(self, t):
        if t.kind == "EOF":
            return "end of input"
        if t.kind == "NL":
            return "end of line"
        if t.kind == "NUM":
            v = t.value
            if isinstance(v, complex):
                return f"'{v.imag:g}i'"
            return f"'{v:g}'"
        return f"'{t.value}'"

    def error(self, msg, tok=None):
        tok = tok or self.tok
        raise MatlabError(msg, tok.line)

    def skip_newlines(self):
        while self.tok.kind == "NL" or self.is_op(";", ","):
            self.next()

    # -- program / statements ------------------------------------------------
    def parse_program(self):
        body = []
        functions = {}
        self.skip_newlines()
        while self.tok.kind != "EOF":
            if self.is_kw("function"):
                f = self.parse_function()
                functions[f.name] = f
            else:
                if self.tok.kind == "KW" and self.tok.value in BLOCK_END:
                    self.error(f"Unexpected '{self.tok.value}'.")
                body.append(self.parse_statement())
            self.skip_newlines()
        return A.Program(body, functions)

    def parse_block(self):
        body = []
        self.skip_newlines()
        while not (self.tok.kind == "EOF" or (
                self.tok.kind == "KW" and self.tok.value in BLOCK_END)):
            body.append(self.parse_statement())
            self.skip_newlines()
        return body

    def end_of_statement(self):
        """Consume the statement terminator; return True if output is shown."""
        t = self.tok
        if t.kind == "OP" and t.value == ";":
            self.next()
            if self.tok.kind == "NL":
                self.next()
            return False
        if t.kind == "OP" and t.value == ",":
            self.next()
            return True
        if t.kind == "NL":
            self.next()
            return True
        if t.kind == "EOF":
            return True
        if t.kind == "KW" and t.value in BLOCK_END:
            return True
        if t.kind in ("NUM", "IDENT", "STR") or (t.kind == "OP" and t.value in ("(", "[")):
            self.error(f"Invalid expression near {self.describe(t)}. Check for a missing operator "
                       f"(+ - * /) or a missing comma or semicolon.")
        self.error(f"Unexpected {self.describe(t)}; expected end of statement.")

    def parse_statement(self):
        t = self.tok
        line = t.line
        if t.kind == "KW":
            kw = t.value
            if kw == "if":
                return self.parse_if()
            if kw == "for":
                return self.parse_for()
            if kw == "while":
                return self.parse_while()
            if kw == "switch":
                return self.parse_switch()
            if kw == "break":
                self.next(); self.end_of_statement()
                return A.Break(line=line)
            if kw == "continue":
                self.next(); self.end_of_statement()
                return A.Continue(line=line)
            if kw == "return":
                self.next(); self.end_of_statement()
                return A.Return(line=line)
            self.error(f"Unexpected keyword '{kw}'.")

        # Command syntax produced by the lexer: IDENT CMDARGS
        if t.kind == "IDENT" and self.peek().kind == "CMDARGS":
            name = self.next().value
            args = self.next().value
            show = self.end_of_statement()
            return A.Command(name, args, show, line=line)

        # Multiple assignment: [a, b] = f(...)
        if self.is_op("[") and self._looks_like_multi_assign():
            targets = self.parse_multi_targets()
            self.expect_op("=")
            expr = self.parse_expr()
            show = self.end_of_statement()
            return A.Assign(targets, expr, show, line=line)

        expr = self.parse_expr()
        if self.is_op("="):
            if not isinstance(expr, (A.Id, A.Index, A.Field)):
                self.error("Invalid left-hand side of assignment.")
            self.next()
            rhs = self.parse_expr()
            show = self.end_of_statement()
            return A.Assign([expr], rhs, show, line=line)
        show = self.end_of_statement()
        return A.ExprStmt(expr, show, line=line)

    def _looks_like_multi_assign(self):
        depth = 0
        j = self.p
        while j < len(self.toks):
            t = self.toks[j]
            if t.kind in ("NL", "EOF"):
                return False
            if t.kind == "OP" and t.value in "[({":
                depth += 1
            elif t.kind == "OP" and t.value in "])}":
                depth -= 1
                if depth == 0:
                    nxt = self.toks[j + 1]
                    return nxt.kind == "OP" and nxt.value == "="
            j += 1
        return False

    def parse_multi_targets(self):
        self.expect_op("[")
        targets = []
        while not self.is_op("]"):
            if self.is_op(","):
                self.next()
                continue
            if self.is_op("~"):
                tok = self.next()
                targets.append(A.Id("~", line=tok.line))
                continue
            targets.append(self.parse_postfix())
        self.expect_op("]")
        return targets

    def parse_if(self):
        line = self.expect_kw("if").line
        clauses = []
        cond = self.parse_expr()
        body = self.parse_block()
        clauses.append((cond, body))
        orelse = None
        while True:
            if self.is_kw("elseif"):
                self.next()
                cond = self.parse_expr()
                clauses.append((cond, self.parse_block()))
            elif self.is_kw("else"):
                self.next()
                orelse = self.parse_block()
            else:
                break
        self.expect_kw("end")
        return A.If(clauses, orelse, line=line)

    def parse_for(self):
        line = self.expect_kw("for").line
        paren = False
        if self.is_op("("):
            paren = True
            self.next()
        if self.tok.kind != "IDENT":
            self.error("Expected loop variable after 'for'.")
        var = self.next().value
        self.expect_op("=")
        expr = self.parse_expr()
        if paren:
            self.expect_op(")")
        body = self.parse_block()
        self.expect_kw("end")
        return A.For(var, expr, body, line=line)

    def parse_while(self):
        line = self.expect_kw("while").line
        cond = self.parse_expr()
        body = self.parse_block()
        self.expect_kw("end")
        return A.While(cond, body, line=line)

    def parse_switch(self):
        line = self.expect_kw("switch").line
        expr = self.parse_expr()
        self.skip_newlines()
        cases = []
        otherwise = None
        while True:
            if self.is_kw("case"):
                self.next()
                val = self.parse_expr()
                cases.append((val, self.parse_block()))
            elif self.is_kw("otherwise"):
                self.next()
                otherwise = self.parse_block()
            else:
                break
        self.expect_kw("end")
        return A.Switch(expr, cases, otherwise, line=line)

    def parse_function(self):
        line = self.expect_kw("function").line
        if not (self.tok.kind == "IDENT" or self.is_op("[")):
            self.error("Function definition is incomplete. Usage: function y = name(x)")
        outputs = []
        # function [a, b] = name(...)  |  function a = name(...)  |  function name(...)
        if self.is_op("["):
            self.next()
            while not self.is_op("]"):
                if self.is_op(","):
                    self.next()
                    continue
                outputs.append(self.next().value)
            self.next()
            self.expect_op("=")
            name = self.next().value
        else:
            first = self.next().value
            if self.is_op("="):
                self.next()
                outputs = [first]
                name = self.next().value
            else:
                name = first
        params = []
        if self.is_op("("):
            self.next()
            while not self.is_op(")"):
                if self.is_op(","):
                    self.next()
                    continue
                t = self.next()
                params.append("~" if t.value == "~" else t.value)
            self.next()
        body = self.parse_block()
        if self.is_kw("end"):
            self.next()
        return A.FunctionDef(name, params, outputs, body, line=line)

    # -- expressions ---------------------------------------------------------
    def parse_expr(self):
        return self.parse_oror()

    def _binary_chain(self, sub, ops):
        left = sub()
        while self.tok.kind == "OP" and self.tok.value in ops:
            op = self.next()
            right = sub()
            left = A.Binary(op.value, left, right, line=op.line)
        return left

    def parse_oror(self):
        return self._binary_chain(self.parse_andand, {"||"})

    def parse_andand(self):
        return self._binary_chain(self.parse_or, {"&&"})

    def parse_or(self):
        return self._binary_chain(self.parse_and, {"|"})

    def parse_and(self):
        return self._binary_chain(self.parse_cmp, {"&"})

    def parse_cmp(self):
        return self._binary_chain(self.parse_range, CMP_OPS)

    def parse_range(self):
        if self.is_op(":") and self.index_depth > 0 and self.peek().kind == "OP" \
                and self.peek().value in (",", ")", "}"):
            t = self.next()
            return A.Colon(line=t.line)
        start = self.parse_additive()
        if self.is_op(":"):
            t = self.next()
            second = self.parse_additive()
            if self.is_op(":"):
                self.next()
                third = self.parse_additive()
                return A.Range(start, second, third, line=t.line)
            return A.Range(start, None, second, line=t.line)
        return start

    def parse_additive(self):
        return self._binary_chain(self.parse_mul, {"+", "-"})

    def parse_mul(self):
        return self._binary_chain(self.parse_unary, MUL_OPS)

    def parse_unary(self):
        if self.is_op("-", "+", "~"):
            t = self.next()
            operand = self.parse_unary()
            if t.value == "+":
                return operand
            if t.value == "-" and isinstance(operand, A.Num):
                return A.Num(-operand.value, line=t.line)
            return A.Unary(t.value, operand, line=t.line)
        return self.parse_power()

    def parse_power(self):
        base = self.parse_postfix()
        while self.is_op("^", ".^"):
            op = self.next()
            # exponent may carry its own unary sign: 2^-1
            if self.is_op("-", "+", "~"):
                u = self.next()
                exp = self.parse_postfix()
                if u.value == "-":
                    exp = A.Unary("-", exp, line=u.line)
                elif u.value == "~":
                    exp = A.Unary("~", exp, line=u.line)
            else:
                exp = self.parse_postfix()
            base = A.Binary(op.value, base, exp, line=op.line)
        return base

    def parse_args(self, closer):
        args = []
        self.index_depth += 1
        saved_matrix = self.matrix_depth
        self.matrix_depth = 0
        try:
            while not self.is_op(closer):
                if self.is_op(","):
                    self.next()
                    continue
                args.append(self.parse_expr())
                if not self.is_op(",", closer):
                    self.error(f"Expected ',' or '{closer}' in argument list, "
                               f"found {self.describe(self.tok)}.")
            self.next()
        finally:
            self.index_depth -= 1
            self.matrix_depth = saved_matrix
        return args

    def parse_postfix(self):
        node = self.parse_primary()
        while True:
            t = self.tok
            if t.kind != "OP":
                break
            # Inside a matrix, `a (1)` with a space is two elements; the lexer
            # already inserted a comma in that case.
            if t.value == "(":
                self.next()
                node = A.Index(node, self.parse_args(")"), False, line=t.line)
            elif t.value == "{" and not t.space_before:
                self.next()
                node = A.Index(node, self.parse_args("}"), True, line=t.line)
            elif t.value == "." and self.peek().kind == "IDENT":
                self.next()
                name = self.next().value
                node = A.Field(node, name, line=t.line)
            elif t.value in ("'", ".'"):
                self.next()
                node = A.Postfix(t.value, node, line=t.line)
            else:
                break
        return node

    def parse_primary(self):
        t = self.tok
        if t.kind == "NUM":
            self.next()
            return A.Num(t.value, line=t.line)
        if t.kind == "STR":
            self.next()
            return A.Str(t.value, line=t.line)
        if t.kind == "IDENT":
            self.next()
            return A.Id(t.value, line=t.line)
        if t.kind == "KW" and t.value == "end" and self.index_depth > 0:
            self.next()
            return A.End(line=t.line)
        if t.kind == "OP":
            if t.value == "(":
                self.next()
                saved_i, saved_m = self.index_depth, self.matrix_depth
                self.matrix_depth = 0
                e = self.parse_expr()
                self.matrix_depth = saved_m
                self.index_depth = saved_i
                self.expect_op(")")
                return e
            if t.value in ("[", "{"):
                return self.parse_matrix()
            if t.value == "@":
                self.next()
                if self.is_op("("):
                    self.next()
                    params = []
                    while not self.is_op(")"):
                        if self.is_op(","):
                            self.next()
                            continue
                        params.append(self.next().value)
                    self.next()
                    saved = self.index_depth
                    self.index_depth = 0
                    body = self.parse_expr()
                    self.index_depth = saved
                    return A.AnonFunc(params, body, line=t.line)
                if self.tok.kind == "IDENT":
                    return A.FuncHandle(self.next().value, line=t.line)
                self.error("Invalid function handle.")
            if t.value == ":" and self.index_depth > 0:
                self.next()
                return A.Colon(line=t.line)
        self.error(f"Unexpected {self.describe(t)} in expression.")

    def parse_matrix(self):
        open_tok = self.next()
        closer = "]" if open_tok.value == "[" else "}"
        rows = [[]]
        self.matrix_depth += 1
        try:
            while not self.is_op(closer):
                if self.is_op(";"):
                    self.next()
                    rows.append([])
                    continue
                if self.is_op(","):
                    self.next()
                    continue
                if self.tok.kind == "NL":
                    self.next()
                    rows.append([])
                    continue
                if self.tok.kind == "EOF":
                    self.error(f"Missing '{closer}'.", open_tok)
                rows[-1].append(self.parse_expr())
            self.next()
        finally:
            self.matrix_depth -= 1
        rows = [r for r in rows if r]
        return A.Matrix(rows, cell=(closer == "}"), line=open_tok.line)


def parse(src):
    return Parser(tokenize(src)).parse_program()
