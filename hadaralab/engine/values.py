"""Runtime value types and MATLAB-style display formatting.

Values in the interpreter are:
  * numpy 2-D arrays (double, complex or logical) - every number is a matrix
  * str          - character row vector
  * Struct       - struct with named fields
  * Cell         - cell array (list of values, 2-D shape)
  * FunctionHandle
  * TransferFunction (from hadaralab.control)
"""

import numpy as np

from ..control.tf import TransferFunction


class Struct(dict):
    pass


class Cell:
    def __init__(self, items, shape=None):
        self.items = list(items)
        self.shape = shape or (1, len(self.items))

    def __len__(self):
        return len(self.items)


class FunctionHandle:
    def __init__(self, name=None, params=None, body=None, closure=None, text=""):
        self.name = name          # named handle: @sin
        self.params = params      # anonymous: @(x) ...
        self.body = body
        self.closure = closure or {}
        self.text = text

    def __repr__(self):
        return "@" + self.name if self.name else self.text


class Multi(tuple):
    """Multiple return values from a builtin."""


# ---------------------------------------------------------------------------
# conversions
# ---------------------------------------------------------------------------

def to_array(v):
    """Coerce a value to a 2-D numpy array."""
    if isinstance(v, np.ndarray):
        if v.ndim == 2:
            return v
        if v.ndim == 0:
            return v.reshape(1, 1)
        if v.ndim == 1:
            return v.reshape(1, -1)
        return v
    if isinstance(v, str):
        if v == "":
            return np.zeros((0, 0))
        return np.array([[float(ord(c)) for c in v]])
    if isinstance(v, (bool, np.bool_)):
        return np.array([[bool(v)]])
    if isinstance(v, (int, float, complex, np.number)):
        return np.array([[v]])
    if isinstance(v, (list, tuple)):
        arr = np.asarray(v)
        return to_array(arr)
    raise TypeError(f"Cannot use a value of type '{class_name(v)}' as a number.")


def scalar(v, what="value"):
    a = to_array(v)
    if a.size != 1:
        raise ValueError(f"Expected a scalar {what}.")
    x = a.ravel()[0]
    if isinstance(x, (complex, np.complexfloating)) and x.imag == 0:
        x = x.real
    return x


def vector(v):
    return to_array(v).ravel(order="F")


def row(x):
    return np.asarray(x).reshape(1, -1)


def col(x):
    return np.asarray(x).reshape(-1, 1)


def simplify(a):
    """Drop a zero imaginary part like MATLAB does."""
    if isinstance(a, np.ndarray) and np.iscomplexobj(a):
        if a.size == 0 or np.all(a.imag == 0):
            return a.real.copy()
    return a


def is_true(v):
    if isinstance(v, str):
        return len(v) > 0 and all(c != "\0" for c in v)
    if isinstance(v, TransferFunction):
        return True
    a = to_array(v)
    if a.size == 0:
        return False
    if np.iscomplexobj(a):
        return bool(np.all(a != 0))
    if np.any(np.isnan(a.astype(float))):
        raise ValueError("NaN's cannot be converted to logicals.")
    return bool(np.all(a != 0))


def class_name(v):
    if isinstance(v, str):
        return "char"
    if isinstance(v, TransferFunction):
        return "ss" if v.ss is not None else "tf"
    if isinstance(v, Struct):
        return "struct"
    if isinstance(v, Cell):
        return "cell"
    if isinstance(v, FunctionHandle):
        return "function_handle"
    if isinstance(v, np.ndarray):
        if v.dtype == bool:
            return "logical"
        return "double"
    return type(v).__name__


def size_of(v):
    if isinstance(v, str):
        return (1, len(v)) if v else (0, 0)
    if isinstance(v, np.ndarray):
        return v.shape if v.ndim == 2 else to_array(v).shape
    if isinstance(v, Cell):
        return v.shape
    return (1, 1)


# ---------------------------------------------------------------------------
# display
# ---------------------------------------------------------------------------

def fmt_real(x, long=False):
    if np.isnan(x):
        return "NaN"
    if np.isinf(x):
        return "Inf" if x > 0 else "-Inf"
    if x == int(x) and abs(x) < 1e10:
        return str(int(x))
    if long:
        return f"{x:.15g}"
    ax = abs(x)
    if 1e-3 <= ax < 1e5:
        return f"{x:.4f}"
    return f"{x:.4e}"


def fmt_scalar(x, long=False):
    if isinstance(x, (complex, np.complexfloating)):
        re, im = fmt_real(x.real, long), fmt_real(abs(x.imag), long)
        sign = "-" if x.imag < 0 else "+"
        return f"{re} {sign} {im}i"
    if isinstance(x, (bool, np.bool_)):
        return "1" if x else "0"
    return fmt_real(float(x), long)


def format_matrix(a, long=False):
    """Format a 2-D array as aligned columns (no header)."""
    a = to_array(a)
    if a.size == 0:
        return "     []"
    if a.dtype == bool:
        a = a.astype(int)
    real = not np.iscomplexobj(a)
    finite = a[np.isfinite(a)] if real else a[np.isfinite(a)].real
    all_int = real and np.all(np.isfinite(a) | np.isnan(a) | np.isinf(a)) and \
        np.all((a[np.isfinite(a)] == np.round(a[np.isfinite(a)]))) and \
        (finite.size == 0 or np.max(np.abs(finite)) < 1e9)
    scale = 1.0
    header = ""
    if real and not all_int and finite.size and not long:
        mx = np.max(np.abs(finite))
        if mx >= 1e5 or (mx < 1e-3 and mx > 0):
            e = int(np.floor(np.log10(mx)))
            scale = 10.0 ** e
            header = f"   1.0e{'+' if e >= 0 else '-'}{abs(e):02d} *\n\n"
    cells = []
    for i in range(a.shape[0]):
        r = []
        for j in range(a.shape[1]):
            x = a[i, j]
            if all_int and real:
                r.append(fmt_real(float(x)))
            elif real:
                v = float(x) / scale
                if np.isnan(v) or np.isinf(v) or v == 0:
                    r.append(fmt_real(v))
                elif long:
                    r.append(f"{v:.15f}")
                else:
                    r.append(f"{v:.4f}")
            else:
                r.append(fmt_scalar(complex(x), long))
        cells.append(r)
    width = max(len(c) for r in cells for c in r)
    width = max(width, 4)
    lines = []
    for r in cells:
        lines.append("".join(("   " + c.rjust(width)) for c in r))
    return header + "\n".join(lines)


def format_value(name, v, long=False):
    """Text shown when a statement is not terminated with ';'."""
    if isinstance(v, str):
        return f"{name} =\n\n    '{v}'\n"
    if isinstance(v, TransferFunction):
        if v.ss is not None:
            parts = [f"{name} =\n"]
            for label, M in zip("ABCD", v.ss):
                parts.append(f"  {label} = \n{format_matrix(M, long)}\n")
            parts.append("Continuous-time state-space model.\n")
            return "\n".join(parts)
        body = v.to_str()
        return (f"{name} =\n \n{body}\n \nContinuous-time transfer function.\n")
    if isinstance(v, Struct):
        if not v:
            return f"{name} = \n\n  struct with no fields.\n"
        w = max(len(k) for k in v)
        lines = [f"{name} = \n\n  struct with fields:\n"]
        for k, val in v.items():
            lines.append(f"    {k.rjust(w)}: {inline(val, long)}")
        return "\n".join(lines) + "\n"
    if isinstance(v, Cell):
        return f"{name} =\n\n  {v.shape[0]}x{v.shape[1]} cell array\n\n    " + \
            "    ".join(inline(x) for x in v.items) + "\n"
    if isinstance(v, FunctionHandle):
        return f"{name} =\n\n  function_handle with value:\n\n    {v!r}\n"
    a = to_array(v)
    if a.size == 1:
        return f"{name} = {fmt_scalar(a.ravel()[0], long)}\n"
    if a.size == 0:
        return f"{name} =\n\n     []\n"
    return f"{name} =\n\n{format_matrix(a, long)}\n"


def inline(v, long=False):
    """Short one-line description (used by struct display and workspace)."""
    if isinstance(v, str):
        return f"'{v}'"
    if isinstance(v, TransferFunction):
        from ..control.tf import poly_to_str
        return f"({poly_to_str(v.num)})/({poly_to_str(v.den)})"
    if isinstance(v, Struct):
        return f"1x1 struct"
    if isinstance(v, Cell):
        return f"{v.shape[0]}x{v.shape[1]} cell"
    if isinstance(v, FunctionHandle):
        return repr(v)
    a = to_array(v)
    if a.size == 1:
        return fmt_scalar(a.ravel()[0], long)
    if a.size == 0:
        return "[]"
    if a.size <= 10 and min(a.shape) == 1:
        sep = " " if a.shape[0] == 1 else "; "
        return "[" + sep.join(fmt_scalar(x, long) for x in a.ravel()) + "]"
    return f"{a.shape[0]}x{a.shape[1]} {class_name(a)}"
