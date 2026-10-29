"""Tree-walking interpreter for the HadaraLab language."""

import os

import numpy as np

from . import ast as A
from .errors import MatlabError
from .parser import parse
from .values import (Cell, FunctionHandle, Multi, Struct, class_name,
                     format_value, is_true, scalar, simplify, to_array)
from ..control.tf import TransferFunction


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Return(Exception):
    pass


class StopExecution(MatlabError):
    def __init__(self):
        super().__init__("Execution stopped by user.")


COLON = object()   # marker for a bare ':' index


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

def _num(v):
    if isinstance(v, (Struct, Cell, FunctionHandle)):
        raise MatlabError(f"Operator is not defined for values of class '{class_name(v)}'.")
    return to_array(v)


def _power(a, b):
    if not np.iscomplexobj(a) and not np.iscomplexobj(b):
        af = a.astype(float)
        bf = b.astype(float)
        if np.any((af < 0) & (bf != np.round(bf))):
            return np.power(af.astype(complex), bf)
        return np.power(af, bf)
    return np.power(a.astype(complex), b)


def _broadcast_check(a, b):
    for da, db in zip(a.shape, b.shape):
        if da != db and da != 1 and db != 1:
            raise MatlabError("Arrays have incompatible sizes for this operation.")


def binary_op(op, a, b):
    if isinstance(a, TransferFunction) or isinstance(b, TransferFunction):
        return _tf_op(op, a, b)
    x, y = _num(a), _num(b)
    with np.errstate(all="ignore"):
        if op in ("+", "-", ".*", "./", ".\\", ".^", "==", "~=", "<", "<=",
                  ">", ">=", "&", "|"):
            if x.size != 1 and y.size != 1:
                _broadcast_check(x, y)
        if x.dtype == bool and op not in ("&", "|", "==", "~="):
            x = x.astype(float)
        if y.dtype == bool and op not in ("&", "|", "==", "~="):
            y = y.astype(float)
        if op == "+":
            r = x + y
        elif op == "-":
            r = x - y
        elif op == ".*":
            r = x * y
        elif op == "./":
            r = x / y
        elif op == ".\\":
            r = y / x
        elif op == ".^":
            r = _power(x, y)
        elif op == "*":
            if x.size == 1 or y.size == 1:
                r = x * y
            else:
                if x.shape[1] != y.shape[0]:
                    raise MatlabError(
                        "Incorrect dimensions for matrix multiplication. Check that the "
                        "number of columns in the first matrix matches the number of rows "
                        "in the second matrix. To operate on each element of the matrix "
                        "individually, use TIMES (.*) for elementwise multiplication.")
                r = x @ y
        elif op == "/":
            if y.size == 1:
                r = x / y
            else:
                if x.shape[1] != y.shape[1]:
                    raise MatlabError("Matrix dimensions must agree.")
                r = np.linalg.lstsq(y.T, x.T, rcond=None)[0].T if y.shape[0] != y.shape[1] \
                    else np.linalg.solve(y.T, x.T).T
        elif op == "\\":
            if x.size == 1:
                r = y / x
            else:
                if x.shape[0] != y.shape[0]:
                    raise MatlabError("Matrix dimensions must agree.")
                r = np.linalg.solve(x, y) if x.shape[0] == x.shape[1] \
                    else np.linalg.lstsq(x, y, rcond=None)[0]
        elif op == "^":
            if x.size == 1 and y.size == 1:
                r = _power(x, y)
            elif y.size == 1 and x.shape[0] == x.shape[1]:
                p = scalar(y)
                if p == int(p):
                    p = int(p)
                    r = np.linalg.matrix_power(x, p) if p >= 0 else \
                        np.linalg.matrix_power(np.linalg.inv(x), -p)
                else:
                    from scipy.linalg import fractional_matrix_power
                    r = fractional_matrix_power(x, p)
            else:
                raise MatlabError("Incorrect dimensions for raising a matrix to a power. "
                                  "Check that the matrix is square and the power is a scalar. "
                                  "To operate on each element of the matrix individually, "
                                  "use POWER (.^) for elementwise power.")
        elif op == "==":
            r = x == y
        elif op == "~=":
            r = x != y
        elif op == "<":
            r = x.real < y.real
        elif op == "<=":
            r = x.real <= y.real
        elif op == ">":
            r = x.real > y.real
        elif op == ">=":
            r = x.real >= y.real
        elif op == "&":
            r = (x != 0) & (y != 0)
        elif op == "|":
            r = (x != 0) | (y != 0)
        else:
            raise MatlabError(f"Unknown operator '{op}'.")
    return simplify(np.asarray(r).reshape(np.asarray(r).shape if np.ndim(r) == 2
                                          else (1, -1) if np.ndim(r) == 1 else (1, 1)))


def _tf_op(op, a, b):
    try:
        if op == "+":
            return TransferFunction.coerce(a) + b if isinstance(a, TransferFunction) else b + a
        if op == "-":
            return a - b if isinstance(a, TransferFunction) else -(b - a)
        if op in ("*", ".*"):
            return a * b if isinstance(a, TransferFunction) else b * a
        if op in ("/", "./"):
            if isinstance(a, TransferFunction):
                return a / b
            return TransferFunction.coerce(a) / b
        if op in ("^", ".^"):
            if not isinstance(a, TransferFunction):
                raise MatlabError("A transfer function cannot be used as an exponent.")
            return a ** to_array(b)
    except (ValueError, ZeroDivisionError) as e:
        raise MatlabError(str(e))
    raise MatlabError(f"Operator '{op}' is not supported for transfer functions.")


def unary_op(op, v):
    if isinstance(v, TransferFunction):
        if op == "-":
            return -v
        raise MatlabError(f"Operator '{op}' is not supported for transfer functions.")
    x = _num(v)
    if op == "-":
        return -x.astype(float) if x.dtype == bool else -x
    if op == "~":
        return x == 0
    raise MatlabError(f"Unknown operator '{op}'.")


# ---------------------------------------------------------------------------
# Indexing helpers
# ---------------------------------------------------------------------------

def _index_list(x, n, allow_grow=False):
    if x is COLON:
        return np.arange(n)
    if isinstance(x, str) and x == ":":
        return np.arange(n)
    a = to_array(x)
    if a.dtype == bool:
        flat = a.ravel(order="F")
        if not allow_grow and flat.size > n and np.any(flat[n:]):
            raise MatlabError(f"The logical index contains a true value outside of "
                              f"the array bounds.")
        return np.flatnonzero(flat)
    flat = np.real(a.ravel(order="F")).astype(float)
    if flat.size and (np.any(flat != np.floor(flat)) or np.any(flat < 1)):
        bad = flat[(flat != np.floor(flat)) | (flat < 1)][0]
        raise MatlabError(f"Index in position 1 is invalid. Array indices must be "
                          f"positive integers or logical values. (got {bad:g})")
    idx = flat.astype(np.int64) - 1
    if not allow_grow and idx.size and idx.max() >= n:
        raise MatlabError(f"Index exceeds the number of array elements. Index must "
                          f"not exceed {n}.")
    return idx


def index_array(arr, args):
    """Read arr(args...) for a 2-D numpy array."""
    if len(args) == 0:
        return arr
    if len(args) == 1:
        x = args[0]
        flat = arr.ravel(order="F")
        idx = _index_list(x, flat.size)
        res = flat[idx]
        if x is COLON or (isinstance(x, str) and x == ":"):
            return res.reshape(-1, 1)
        xa = to_array(x) if not isinstance(x, str) else None
        if xa is not None and xa.dtype != bool and xa.ndim == 2 and min(xa.shape) > 1:
            return res.reshape(xa.shape, order="F")
        if arr.shape[0] == 1 and arr.ndim == 2:
            return res.reshape(1, -1)
        if arr.ndim == 2 and arr.shape[1] == 1:
            return res.reshape(-1, 1)
        if xa is not None and xa.shape[0] > 1 and xa.dtype != bool:
            return res.reshape(-1, 1)
        if xa is not None and xa.dtype == bool:
            return res.reshape(-1, 1)
        return res.reshape(1, -1)
    extra = args[2:]
    for e in extra:
        if e is not COLON and not np.all(to_array(e) == 1):
            raise MatlabError("Index exceeds matrix dimensions.")
    i = _index_list(args[0], arr.shape[0])
    j = _index_list(args[1], arr.shape[1])
    if i.size and i.max() >= arr.shape[0]:
        raise MatlabError(f"Index in position 1 exceeds array bounds. Index must not "
                          f"exceed {arr.shape[0]}.")
    if j.size and j.max() >= arr.shape[1]:
        raise MatlabError(f"Index in position 2 exceeds array bounds. Index must not "
                          f"exceed {arr.shape[1]}.")
    return arr[np.ix_(i, j)]


def assign_array(base, args, rhs, delete=False):
    """Return a copy of base with base(args...) = rhs (MATLAB growth rules)."""
    a = np.zeros((0, 0)) if base is None else to_array(base).copy()
    r = to_array(rhs)
    if np.iscomplexobj(r) and not np.iscomplexobj(a):
        a = a.astype(complex)
    elif a.dtype == bool and r.dtype != bool:
        a = a.astype(float)
    elif a.dtype != bool and a.dtype.kind not in "fc":
        a = a.astype(float)
    if a.dtype == bool and r.dtype == bool:
        pass

    if delete:
        if len(args) == 1:
            flat = a.ravel(order="F")
            idx = _index_list(args[0], flat.size)
            keep = np.setdiff1d(np.arange(flat.size), idx)
            res = flat[keep]
            return res.reshape(-1, 1) if a.shape[1] == 1 and a.shape[0] > 1 else res.reshape(1, -1)
        i_all = args[0] is COLON
        j_all = args[1] is COLON
        if i_all:
            j = _index_list(args[1], a.shape[1])
            return np.delete(a, j, axis=1)
        if j_all:
            i = _index_list(args[0], a.shape[0])
            return np.delete(a, i, axis=0)
        raise MatlabError("A null assignment can have only one non-colon index.")

    if len(args) == 1:
        x = args[0]
        if x is COLON:
            if r.size == 1:
                a[...] = r.ravel()[0]
                return a
            if r.size != a.size:
                raise MatlabError("Unable to perform assignment because the left and "
                                  "right sides have a different number of elements.")
            return r.ravel(order="F").reshape(a.shape, order="F").astype(a.dtype)
        idx = _index_list(x, a.size, allow_grow=True)
        need = int(idx.max()) + 1 if idx.size else 0
        if need > a.size:
            if a.size == 0:
                a = np.zeros((1, need), dtype=a.dtype if a.dtype != bool else float)
            elif a.shape[0] == 1:
                a = np.concatenate([a, np.zeros((1, need - a.shape[1]), dtype=a.dtype)], axis=1)
            elif a.shape[1] == 1:
                a = np.concatenate([a, np.zeros((need - a.shape[0], 1), dtype=a.dtype)], axis=0)
            else:
                raise MatlabError("Attempt to grow array along ambiguous dimension.")
        flat = a.ravel(order="F").copy()
        if r.size == 1:
            flat[idx] = r.ravel()[0]
        elif r.size == idx.size:
            flat[idx] = r.ravel(order="F")
        else:
            raise MatlabError("Unable to perform assignment because the left and right "
                              "sides have a different number of elements.")
        return flat.reshape(a.shape, order="F")

    i_arg, j_arg = args[0], args[1]
    ni = a.shape[0] if i_arg is not COLON or a.shape[0] else (r.shape[0] if r.size > 1 else 1)
    nj = a.shape[1] if j_arg is not COLON or a.shape[1] else (r.shape[1] if r.size > 1 else 1)
    if i_arg is COLON and a.shape[0] == 0:
        ni = r.shape[0] if r.size > 1 else 1
    if j_arg is COLON and a.shape[1] == 0:
        nj = r.shape[1] if r.size > 1 else 1
    i = _index_list(i_arg, ni, allow_grow=True)
    j = _index_list(j_arg, nj, allow_grow=True)
    rows = max(a.shape[0], int(i.max()) + 1 if i.size else 0, ni if i_arg is COLON else 0)
    cols = max(a.shape[1], int(j.max()) + 1 if j.size else 0, nj if j_arg is COLON else 0)
    if (rows, cols) != a.shape:
        grown = np.zeros((rows, cols), dtype=a.dtype)
        grown[:a.shape[0], :a.shape[1]] = a
        a = grown
    if r.size == 1:
        a[np.ix_(i, j)] = r.ravel()[0]
    elif r.size == i.size * j.size:
        a[np.ix_(i, j)] = r.reshape(i.size, j.size) if r.shape == (i.size, j.size) \
            else r.ravel(order="F").reshape((i.size, j.size), order="F")
    else:
        raise MatlabError(f"Unable to perform assignment because the size of the left "
                          f"side is {i.size}-by-{j.size} and the size of the right side "
                          f"is {r.shape[0]}-by-{r.shape[1]}.")
    return a


def unparse(node):
    """Turn an expression AST back into source text (for function handles)."""
    if isinstance(node, A.Num):
        v = node.value
        if isinstance(v, complex):
            return f"{v.imag:g}i"
        return f"{v:g}"
    if isinstance(node, A.Str):
        return "'" + node.value.replace("'", "''") + "'"
    if isinstance(node, A.Id):
        return node.name
    if isinstance(node, A.Colon):
        return ":"
    if isinstance(node, A.End):
        return "end"
    if isinstance(node, A.Binary):
        return f"{unparse(node.left)}{node.op}{unparse(node.right)}"
    if isinstance(node, A.Unary):
        return f"{node.op}{unparse(node.operand)}"
    if isinstance(node, A.Postfix):
        return f"{unparse(node.operand)}{node.op}"
    if isinstance(node, A.Index):
        o, c = ("{", "}") if node.brace else ("(", ")")
        return f"{unparse(node.target)}{o}{','.join(unparse(a) for a in node.args)}{c}"
    if isinstance(node, A.Field):
        return f"{unparse(node.target)}.{node.name}"
    if isinstance(node, A.Matrix):
        o, c = ("{", "}") if node.cell else ("[", "]")
        return o + ";".join(",".join(unparse(e) for e in r) for r in node.rows) + c
    if isinstance(node, A.Range):
        if node.step is None:
            return f"{unparse(node.start)}:{unparse(node.stop)}"
        return f"{unparse(node.start)}:{unparse(node.step)}:{unparse(node.stop)}"
    if isinstance(node, A.AnonFunc):
        return f"@({','.join(node.params)}){unparse(node.body)}"
    if isinstance(node, A.FuncHandle):
        return "@" + node.name
    return "?"


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------

class Interpreter:
    def __init__(self, output=None, figures=None):
        from .builtins import BUILTINS
        from ..graphics import FigureManager
        self.builtins = BUILTINS
        self.base = {}
        self.vars = self.base
        self.functions = {}
        self.search_path = []
        self.cwd = os.getcwd()
        self.out = output or (lambda s: print(s, end=""))
        self.figures = figures or FigureManager()
        self.format_long = False
        self.stop_requested = False
        self.end_stack = []
        self.depth = 0
        self.line = 0
        self.on_clc = None
        self.on_workspace_changed = None

    # -- public API ----------------------------------------------------------
    def write(self, text):
        self.out(text)

    def execute(self, src, filename=None):
        """Run source code in the base workspace. Raises MatlabError."""
        self.stop_requested = False
        prog = parse(src)
        self.functions.update(prog.functions)
        self.vars = self.base
        self.depth = 0
        try:
            self.exec_block(prog.body)
        except (_Break, _Continue):
            pass
        except _Return:
            pass

    def exec_block(self, body):
        for stmt in body:
            self.exec_stmt(stmt)

    def check_stop(self):
        if self.stop_requested:
            self.stop_requested = False
            raise StopExecution()

    # -- statements ----------------------------------------------------------
    def exec_stmt(self, s):
        self.line = s.line
        self.check_stop()
        try:
            self._exec_stmt(s)
        except (_Break, _Continue, _Return):
            raise
        except MatlabError as e:
            if e.line is None:
                e.line = s.line
            raise
        except RecursionError:
            raise MatlabError("Maximum recursion limit reached.", s.line)
        except np.linalg.LinAlgError as e:
            raise MatlabError(f"Linear algebra error: {e}", s.line)
        except Exception as e:  # turn Python errors into MATLAB-style errors
            raise MatlabError(str(e) or type(e).__name__, s.line)

    def _exec_stmt(self, s):
        t = type(s)
        if t is A.ExprStmt:
            self.exec_expr_stmt(s)
        elif t is A.Assign:
            self.exec_assign(s)
        elif t is A.If:
            for cond, body in s.clauses:
                if is_true(self.eval(cond)):
                    self.exec_block(body)
                    return
            if s.orelse is not None:
                self.exec_block(s.orelse)
        elif t is A.For:
            self.exec_for(s)
        elif t is A.While:
            while is_true(self.eval(s.cond)):
                self.check_stop()
                try:
                    self.exec_block(s.body)
                except _Break:
                    break
                except _Continue:
                    continue
        elif t is A.Switch:
            self.exec_switch(s)
        elif t is A.Break:
            raise _Break()
        elif t is A.Continue:
            raise _Continue()
        elif t is A.Return:
            raise _Return()
        elif t is A.Command:
            outs = self.call_function(s.name, list(s.args), 0)
            if outs and s.show:
                self.base_assign_ans(outs[0], s.show)
        else:
            raise MatlabError(f"Unsupported statement {t.__name__}.")

    def base_assign_ans(self, value, show):
        self.vars["ans"] = value
        if show:
            self.write(format_value("ans", value, self.format_long) + "\n")

    def exec_expr_stmt(self, s):
        e = s.expr
        if isinstance(e, A.Id) and e.name in self.vars:
            if s.show:
                self.write(format_value(e.name, self.vars[e.name], self.format_long) + "\n")
            return
        outs = self.eval_multi(e, 0)
        if outs:
            self.base_assign_ans(outs[0], s.show)

    def exec_assign(self, s):
        if len(s.targets) == 1:
            value = self.eval(s.expr)
            self.assign_to(s.targets[0], value)
            if s.show:
                name = self.root_name(s.targets[0])
                self.write(format_value(name, self.vars[name], self.format_long) + "\n")
            return
        outs = self.eval_multi(s.expr, len(s.targets))
        if len(outs) < len([t for t in s.targets]):
            raise MatlabError("Too many output arguments.")
        for target, value in zip(s.targets, outs):
            if isinstance(target, A.Id) and target.name == "~":
                continue
            self.assign_to(target, value)
            if s.show:
                name = self.root_name(target)
                self.write(format_value(name, self.vars[name], self.format_long) + "\n")

    def root_name(self, node):
        while not isinstance(node, A.Id):
            node = node.target
        return node.name

    def exec_for(self, s):
        v = self.eval(s.expr)
        if isinstance(v, Cell):
            items = [Cell([x]) for x in v.items]
        elif isinstance(v, str):
            items = list(v)
        elif isinstance(v, TransferFunction):
            items = [v]
        else:
            arr = to_array(v)
            if arr.size == 0:
                items = []
            elif arr.shape[0] == 1:
                items = [arr[:, k:k + 1] for k in range(arr.shape[1])]
            else:
                items = [arr[:, k:k + 1] for k in range(arr.shape[1])]
        for item in items:
            self.check_stop()
            self.vars[s.var] = item
            try:
                self.exec_block(s.body)
            except _Break:
                break
            except _Continue:
                continue

    def exec_switch(self, s):
        v = self.eval(s.expr)

        def matches(cv):
            if isinstance(cv, Cell):
                return any(matches(x) for x in cv.items)
            if isinstance(v, str) or isinstance(cv, str):
                return isinstance(v, str) and isinstance(cv, str) and v == cv
            a, b = to_array(v), to_array(cv)
            return a.size == 1 and b.size == 1 and a.ravel()[0] == b.ravel()[0]

        for cexpr, body in s.cases:
            if matches(self.eval(cexpr)):
                self.exec_block(body)
                return
        if s.otherwise is not None:
            self.exec_block(s.otherwise)

    # -- assignment ----------------------------------------------------------
    def try_get(self, node):
        if isinstance(node, A.Id):
            return self.vars.get(node.name)
        if isinstance(node, A.Field):
            base = self.try_get(node.target)
            if isinstance(base, Struct):
                return base.get(node.name)
            return None
        if isinstance(node, A.Index):
            base = self.try_get(node.target)
            if base is None:
                return None
            return self.index_value(base, node.args, node.brace)
        return None

    def assign_to(self, node, value):
        if isinstance(node, A.Id):
            self.vars[node.name] = value
            return
        if isinstance(node, A.Field):
            base = self.try_get(node.target)
            if base is None:
                base = Struct()
            if not isinstance(base, Struct):
                raise MatlabError("Field assignment to a non-structure array object.")
            new = Struct(base)
            new[node.name] = value
            self.assign_to(node.target, new)
            return
        if isinstance(node, A.Index):
            base = self.try_get(node.target)
            if isinstance(base, Cell) or (base is None and node.brace):
                new = self.assign_cell(base, node, value)
            elif node.brace:
                raise MatlabError("Brace indexing is not supported for variables of this type.")
            else:
                if isinstance(base, (TransferFunction, Struct, FunctionHandle)):
                    raise MatlabError(f"Indexed assignment is not supported for '{class_name(base)}'.")
                was_str = isinstance(base, str)
                args = self.eval_index_args(node.args, base if base is not None else np.zeros((0, 0)))
                delete = isinstance(value, np.ndarray) and value.size == 0 and \
                    not isinstance(value, str) and base is not None
                if isinstance(value, Cell) or isinstance(value, TransferFunction):
                    raise MatlabError("Conversion to double from "
                                      f"{class_name(value)} is not possible.")
                new = assign_array(base, args, value, delete=delete)
                if was_str or (isinstance(value, str) and (base is None or isinstance(base, str))):
                    new = "".join(chr(int(c)) for c in np.real(new).ravel(order="F"))
            self.assign_to(node.target, new)
            return
        raise MatlabError("Invalid assignment target.")

    def assign_cell(self, base, node, value):
        items = list(base.items) if isinstance(base, Cell) else []
        args = self.eval_index_args(node.args, base if base is not None else Cell([]))
        if len(args) != 1:
            if len(args) == 2 and (to_array(args[0]).size == 1):
                k = int(scalar(args[1])) if to_array(args[0]).ravel()[0] == 1 else None
                if k is None:
                    raise MatlabError("Only row cell arrays are supported.")
                args = [args[1]]
            else:
                raise MatlabError("Only linear indexing of cell arrays is supported.")
        k = int(scalar(args[0])) - 1
        while len(items) <= k:
            items.append(np.zeros((0, 0)))
        items[k] = value if node.brace else (value.items[0] if isinstance(value, Cell) else value)
        return Cell(items)

    # -- expressions ---------------------------------------------------------
    def eval(self, node):
        outs = self.eval_multi(node, 1)
        if not outs:
            name = getattr(node, "name", None) or (
                getattr(node.target, "name", None) if isinstance(node, A.Index) else None)
            raise MatlabError(f"'{name or 'expression'}' does not return a value.")
        return outs[0]

    def eval_multi(self, node, nargout):
        t = type(node)
        if t is A.Num:
            return [np.array([[node.value]])]
        if t is A.Str:
            return [node.value]
        if t is A.Id:
            return self.eval_id(node, nargout)
        if t is A.Binary:
            if node.op == "&&":
                l = self.eval(node.left)
                if not is_true(l):
                    return [np.array([[False]])]
                return [np.array([[is_true(self.eval(node.right))]])]
            if node.op == "||":
                l = self.eval(node.left)
                if is_true(l):
                    return [np.array([[True]])]
                return [np.array([[is_true(self.eval(node.right))]])]
            return [binary_op(node.op, self.eval(node.left), self.eval(node.right))]
        if t is A.Unary:
            return [unary_op(node.op, self.eval(node.operand))]
        if t is A.Postfix:
            v = self.eval(node.operand)
            if isinstance(v, (str, TransferFunction)):
                return [v]
            a = to_array(v)
            return [a.conj().T if node.op == "'" else a.T]
        if t is A.Index:
            return self.eval_index(node, nargout)
        if t is A.Field:
            return [self.get_field(self.eval(node.target), node.name)]
        if t is A.Matrix:
            return [self.eval_matrix(node)]
        if t is A.Range:
            return [self.eval_range(node)]
        if t is A.End:
            return [np.array([[float(self.end_value())]])]
        if t is A.Colon:
            return [":"]
        if t is A.AnonFunc:
            closure = dict(self.vars)
            return [FunctionHandle(params=node.params, body=node.body, closure=closure,
                                   text=unparse(node))]
        if t is A.FuncHandle:
            return [FunctionHandle(name=node.name)]
        raise MatlabError(f"Cannot evaluate {t.__name__}.")

    def eval_id(self, node, nargout):
        name = node.name
        if name in self.vars:
            return [self.vars[name]]
        return self.call_function(name, [], nargout)

    def end_value(self):
        if not self.end_stack:
            raise MatlabError("'end' can only be used inside an index.")
        val, k, n = self.end_stack[-1]
        if isinstance(val, str):
            shape = (1, len(val))
        elif isinstance(val, Cell):
            shape = val.shape
        else:
            shape = to_array(val).shape
        if n == 1:
            return shape[0] * shape[1]
        if k < 2:
            return shape[k] if k < len(shape) else 1
        return 1

    def eval_index_args(self, args, base):
        vals = []
        for k, a in enumerate(args):
            if isinstance(a, A.Colon):
                vals.append(COLON)
                continue
            self.end_stack.append((base, k, len(args)))
            try:
                v = self.eval(a)
            finally:
                self.end_stack.pop()
            if isinstance(v, str) and v == ":":
                v = COLON
            vals.append(v)
        return vals

    def eval_index(self, node, nargout):
        target = node.target
        # Variable indexing vs function call
        if isinstance(target, A.Id) and target.name not in self.vars:
            if node.brace:
                raise MatlabError(f"Undefined variable '{target.name}'.")
            args = []
            for a in node.args:
                if isinstance(a, A.Colon):
                    args.append(":")
                else:
                    args.append(self.eval(a))
            # variable names of the arguments (used for plot legends)
            self.arg_names = [a.name if isinstance(a, A.Id) else None for a in node.args]
            return self.call_function(target.name, args, nargout)
        base = self.eval(target)
        if isinstance(base, FunctionHandle):
            args = [self.eval(a) for a in node.args]
            return self.call_handle(base, args, nargout)
        if isinstance(base, TransferFunction):
            # G(s) -> evaluate at complex frequency s
            args = [self.eval(a) for a in node.args]
            if len(args) == 1:
                s = to_array(args[0])
                return [simplify(np.asarray(base(s.astype(complex))))]
            if all(to_array(a).size == 1 and scalar(a) == 1 for a in args):
                return [base]
            raise MatlabError("Transfer functions are SISO; use G(s) to evaluate.")
        return [self.index_value(base, node.args, node.brace, evaluated=False)]

    def index_value(self, base, args, brace=False, evaluated=False):
        vals = args if evaluated else self.eval_index_args(args, base)
        if isinstance(base, Cell):
            idx = _index_list(vals[0] if len(vals) == 1 else vals[-1], len(base.items))
            if brace:
                if len(idx) != 1:
                    raise MatlabError("Brace indexing with multiple elements is not supported here.")
                return base.items[int(idx[0])]
            return Cell([base.items[i] for i in idx])
        if brace:
            raise MatlabError("Brace indexing is not supported for variables of this type.")
        if isinstance(base, str):
            codes = np.array([[float(ord(c)) for c in base]]) if base else np.zeros((0, 0))
            res = index_array(codes, vals)
            return "".join(chr(int(c)) for c in res.ravel(order="F"))
        if isinstance(base, Struct):
            if all(v is not COLON and to_array(v).size == 1 and scalar(v) == 1 for v in vals):
                return base
            raise MatlabError("Index exceeds the number of array elements.")
        if isinstance(base, (TransferFunction, FunctionHandle)):
            raise MatlabError(f"Cannot index into a value of class '{class_name(base)}'.")
        return index_array(to_array(base), vals)

    def get_field(self, v, name):
        if isinstance(v, Struct):
            if name not in v:
                raise MatlabError(f"Unrecognized field name \"{name}\".")
            return v[name]
        if isinstance(v, TransferFunction):
            key = name.lower()
            if key in ("num", "numerator"):
                return v.num.reshape(1, -1)
            if key in ("den", "denominator"):
                return v.den.reshape(1, -1)
            if key == "name":
                return v.name
            if key == "variable":
                return "s"
            raise MatlabError(f"No property named '{name}' for tf objects.")
        raise MatlabError(f"Dot indexing is not supported for variables of this type "
                          f"('{class_name(v)}').")

    def eval_matrix(self, node):
        if node.cell:
            rows = [[self.eval(e) for e in r] for r in node.rows]
            if not rows:
                return Cell([], (0, 0))
            items = [x for r in rows for x in r]
            return Cell(items, (len(rows), len(rows[0])) if len(rows) > 0 else (0, 0))
        built_rows = []
        for r in node.rows:
            vals = [self.eval(e) for e in r]
            built_rows.append(self.concat_row(vals))
        built_rows = [b for b in built_rows if not (isinstance(b, np.ndarray) and b.size == 0)]
        if not built_rows:
            return np.zeros((0, 0))
        if len(built_rows) == 1:
            return built_rows[0]
        if any(isinstance(b, str) for b in built_rows):
            if all(isinstance(b, str) for b in built_rows):
                lens = {len(b) for b in built_rows}
                if len(lens) != 1:
                    raise MatlabError("Dimensions of arrays being concatenated are not consistent.")
                return "\n".join(built_rows)
            built_rows = [to_array(b) for b in built_rows]
        if any(isinstance(b, (TransferFunction, Cell)) for b in built_rows):
            raise MatlabError("Cannot vertically concatenate these values.")
        arrs = [to_array(b) for b in built_rows]
        widths = {a.shape[1] for a in arrs}
        if len(widths) != 1:
            raise MatlabError("Dimensions of arrays being concatenated are not consistent.")
        return simplify(np.vstack(arrs))

    def concat_row(self, vals):
        vals = [v for v in vals if not (isinstance(v, np.ndarray) and v.size == 0)]
        if not vals:
            return np.zeros((0, 0))
        if any(isinstance(v, str) for v in vals):
            parts = []
            for v in vals:
                if isinstance(v, str):
                    parts.append(v)
                else:
                    parts.append("".join(chr(int(c)) for c in to_array(v).real.ravel()))
            return "".join(parts)
        if any(isinstance(v, Cell) for v in vals):
            items = []
            for v in vals:
                items.extend(v.items if isinstance(v, Cell) else [v])
            return Cell(items)
        if any(isinstance(v, TransferFunction) for v in vals):
            if len(vals) == 1:
                return vals[0]
            raise MatlabError("Arrays of transfer functions are not supported; "
                              "use separate variables.")
        if any(isinstance(v, (Struct, FunctionHandle)) for v in vals):
            if len(vals) == 1:
                return vals[0]
            raise MatlabError("Cannot concatenate these values.")
        if len(vals) == 1:
            return to_array(vals[0])
        arrs = [to_array(v) for v in vals]
        heights = {a.shape[0] for a in arrs}
        if len(heights) != 1:
            raise MatlabError("Dimensions of arrays being concatenated are not consistent.")
        if all(a.dtype == bool for a in arrs):
            return np.hstack(arrs)
        return simplify(np.hstack([a.astype(complex) if np.iscomplexobj(a) else a.astype(float)
                                   for a in arrs]))

    def eval_range(self, node):
        start = float(np.real(scalar(self.eval(node.start), "range start")))
        step = 1.0 if node.step is None else float(np.real(scalar(self.eval(node.step), "range step")))
        stop = float(np.real(scalar(self.eval(node.stop), "range end")))
        if step == 0 or (step > 0 and start > stop) or (step < 0 and start < stop):
            return np.zeros((1, 0))
        n = int(np.floor((stop - start) / step + 1e-10)) + 1
        if n > 50_000_000:
            raise MatlabError("Requested array is too large.")
        return (start + step * np.arange(n)).reshape(1, -1)

    # -- calls ---------------------------------------------------------------
    def call_function(self, name, args, nargout):
        if name in self.functions:
            return self.call_user(self.functions[name], args, nargout)
        f = self.builtins.get(name)
        if f is None:
            fdef = self.find_m_file(name)
            if fdef is not None:
                return self.call_user(fdef, args, nargout)
            raise MatlabError(f"Undefined function or variable '{name}'.")
        try:
            res = f(self, args, nargout)
        except IndexError as e:
            # a builtin read args[k] that was not given
            if "list index" in str(e) or "tuple index" in str(e):
                raise MatlabError(f"Not enough input arguments for '{name}'. Type  help {name}  for usage.")
            raise
        if res is None:
            return []
        if isinstance(res, Multi):
            return list(res)
        return [res]

    def find_m_file(self, name):
        for d in [self.cwd] + self.search_path:
            path = os.path.join(d, name + ".m")
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    prog = parse(fh.read())
                if name in prog.functions:
                    self.functions.update(prog.functions)
                    return prog.functions[name]
                # script file: run it like a function without arguments
                return A.FunctionDef(name, [], [], prog.body)
        return None

    def call_user(self, fdef, args, nargout):
        if len(args) > len(fdef.params) and not (fdef.params and fdef.params[-1] == "varargin"):
            raise MatlabError(f"Too many input arguments for function '{fdef.name}'.")
        if self.depth > 200:
            raise MatlabError("Maximum recursion limit of 200 reached.")
        is_script = not fdef.params and not fdef.outputs and not args and fdef.line == 0
        if is_script:
            self.exec_block(fdef.body)
            return []
        frame = {}
        params = fdef.params
        if params and params[-1] == "varargin":
            fixed = params[:-1]
            for p, v in zip(fixed, args):
                frame[p] = v
            frame["varargin"] = Cell(args[len(fixed):])
        else:
            for p, v in zip(params, args):
                if p != "~":
                    frame[p] = v
        frame["nargin"] = np.array([[float(len(args))]])
        frame["nargout"] = np.array([[float(nargout)]])
        saved_vars, saved_line = self.vars, self.line
        self.vars = frame
        self.depth += 1
        try:
            try:
                self.exec_block(fdef.body)
            except _Return:
                pass
            except (_Break, _Continue):
                pass
            outs = []
            for k, o in enumerate(fdef.outputs):
                if k >= max(nargout, 1):
                    break
                if o not in frame:
                    if k == 0 and nargout == 0:
                        break
                    raise MatlabError(f"Output argument '{o}' (and possibly others) not "
                                      f"assigned a value in the execution with "
                                      f"'{fdef.name}' function.")
                outs.append(frame[o])
            return outs
        finally:
            self.depth -= 1
            self.vars = saved_vars
            self.line = saved_line

    def call_handle(self, h, args, nargout=1):
        if not isinstance(h, FunctionHandle):
            raise MatlabError("Expected a function handle.")
        if h.name:
            if h.name in self.vars and isinstance(self.vars[h.name], FunctionHandle):
                return self.call_handle(self.vars[h.name], args, nargout)
            return self.call_function(h.name, args, max(nargout, 1))
        if len(args) > len(h.params):
            raise MatlabError(f"Too many input arguments for {h.text} "
                              f"(expects {len(h.params)}, got {len(args)}).")
        if len(args) < len(h.params):
            raise MatlabError(f"Not enough input arguments for {h.text} "
                              f"(expects {len(h.params)}, got {len(args)}).")
        frame = dict(h.closure)
        for p, v in zip(h.params, args):
            frame[p] = v
        saved = self.vars
        self.vars = frame
        try:
            return self.eval_multi(h.body, max(nargout, 1))
        finally:
            self.vars = saved

    def call_value(self, h, *args):
        """Convenience for builtins: call a handle and return its first output."""
        outs = self.call_handle(h, list(args), 1)
        if not outs:
            raise MatlabError("Function handle did not return a value.")
        return outs[0]
