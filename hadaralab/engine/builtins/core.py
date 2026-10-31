"""Core math, matrix, string and workspace builtins."""

import re
import time

import numpy as np

from . import builtin
from ..errors import MatlabError
from ..values import (Cell, FunctionHandle, Multi, Struct, class_name, col,
                      format_matrix, format_value, row, scalar, simplify,
                      size_of, to_array, vector)
from ...control.tf import TransferFunction, poly_to_str


def nargs(args, lo, hi, name):
    if len(args) < lo:
        raise MatlabError(f"Not enough input arguments for '{name}'.")
    if hi is not None and len(args) > hi:
        raise MatlabError(f"Too many input arguments for '{name}'.")


def num_arg(v, name="argument"):
    if isinstance(v, (TransferFunction, Struct, Cell, FunctionHandle)):
        raise MatlabError(f"Expected a numeric {name}, got '{class_name(v)}'.")
    return to_array(v)


def int_arg(v, name="argument"):
    x = scalar(v, name)
    if np.iscomplexobj(x) or x != int(np.real(x)):
        raise MatlabError(f"{name} must be an integer.")
    return int(np.real(x))


def str_arg(v, name="argument"):
    if not isinstance(v, str):
        raise MatlabError(f"Expected a string (char) for {name}.")
    return v


def arr(x):
    """numpy result -> 2-D MATLAB value."""
    a = np.asarray(x)
    if a.ndim == 0:
        a = a.reshape(1, 1)
    elif a.ndim == 1:
        a = a.reshape(1, -1)
    return simplify(a)


def first_dim(a, dim=None):
    if dim is not None:
        return dim
    return 0 if a.shape[0] != 1 else 1


# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

def _const(value):
    def f(ip, args, nargout):
        if not args:
            return arr(value)
        shape = [int_arg(a) for a in args if not isinstance(a, str)]
        if len(shape) == 1:
            shape = shape * 2
        return np.full(shape, value)
    return f


for _n, _v, _en, _ar in [
        ("pi", np.pi, "The number pi = 3.14159...", "الثابت باي (π)"),
        ("Inf", np.inf, "Infinity", "اللانهاية"),
        ("NaN", np.nan, "Not-a-Number", "قيمة غير عددية"),
        ("eps", np.finfo(float).eps, "Floating-point relative accuracy", "دقة الأعداد العشرية"),
        ("realmax", np.finfo(float).max, "Largest floating-point number", "أكبر عدد عشري"),
        ("realmin", np.finfo(float).tiny, "Smallest positive normalized number", "أصغر عدد موجب")]:
    builtin(_n, sig=_n, en=_en, ar=_ar, cat="Constants")(_const(_v))
builtin("inf", sig="inf", en="Infinity", ar="اللانهاية", cat="Constants")(_const(np.inf))
builtin("nan", sig="nan", en="Not-a-Number", ar="قيمة غير عددية", cat="Constants")(_const(np.nan))


@builtin("i", "j", sig="i", en="Imaginary unit", ar="الوحدة التخيلية", cat="Constants")
def _imag_unit(ip, args, nargout):
    return np.array([[1j]])


@builtin("true", sig="true", en="Logical true", ar="القيمة المنطقية صحيح (true)", cat="Constants")
def _true(ip, args, nargout):
    if args:
        shape = [int_arg(a) for a in args]
        return np.ones(shape * 2 if len(shape) == 1 else shape, dtype=bool)
    return np.array([[True]])


@builtin("false", sig="false", en="Logical false", ar="القيمة المنطقية خطأ (false)", cat="Constants")
def _false(ip, args, nargout):
    if args:
        shape = [int_arg(a) for a in args]
        return np.zeros(shape * 2 if len(shape) == 1 else shape, dtype=bool)
    return np.array([[False]])


# ---------------------------------------------------------------------------
# element-wise math
# ---------------------------------------------------------------------------

def _complex_safe(fn_real, needs_complex):
    def f(x):
        if not np.iscomplexobj(x) and np.any(needs_complex(x)):
            return fn_real(x.astype(complex))
        return fn_real(x)
    return f


_ELEMENTWISE = {
    "abs": (np.abs, "Absolute value / magnitude", "القيمة المطلقة"),
    "sqrt": (_complex_safe(np.sqrt, lambda x: x < 0), "Square root", "الجذر التربيعي"),
    "exp": (np.exp, "Exponential e^x", "الدالة الأسية"),
    "log": (_complex_safe(np.log, lambda x: x < 0), "Natural logarithm", "اللوغاريتم الطبيعي"),
    "log10": (_complex_safe(np.log10, lambda x: x < 0), "Base-10 logarithm", "لوغاريتم للأساس 10"),
    "log2": (_complex_safe(np.log2, lambda x: x < 0), "Base-2 logarithm", "لوغاريتم للأساس 2"),
    "sin": (np.sin, "Sine (radians)", "الجيب"),
    "cos": (np.cos, "Cosine (radians)", "جيب التمام"),
    "tan": (np.tan, "Tangent (radians)", "الظل"),
    "asin": (_complex_safe(np.arcsin, lambda x: np.abs(x) > 1), "Inverse sine", "معكوس الجيب"),
    "acos": (_complex_safe(np.arccos, lambda x: np.abs(x) > 1), "Inverse cosine", "معكوس جيب التمام"),
    "atan": (np.arctan, "Inverse tangent", "معكوس الظل"),
    "sinh": (np.sinh, "Hyperbolic sine", "الجيب الزائدي"),
    "cosh": (np.cosh, "Hyperbolic cosine", "جيب التمام الزائدي"),
    "tanh": (np.tanh, "Hyperbolic tangent", "الظل الزائدي"),
    "sec": (lambda x: 1 / np.cos(x), "Secant", "القاطع"),
    "csc": (lambda x: 1 / np.sin(x), "Cosecant", "قاطع التمام"),
    "cot": (lambda x: 1 / np.tan(x), "Cotangent", "ظل التمام"),
    "floor": (np.floor, "Round toward -Inf", "التقريب للأسفل"),
    "ceil": (np.ceil, "Round toward +Inf", "التقريب للأعلى"),
    "fix": (np.trunc, "Round toward zero", "التقريب نحو الصفر"),
    "sign": (np.sign, "Sign function", "دالة الإشارة"),
    "real": (np.real, "Real part", "الجزء الحقيقي"),
    "imag": (np.imag, "Imaginary part", "الجزء التخيلي"),
    "conj": (np.conj, "Complex conjugate", "المرافق"),
    "angle": (np.angle, "Phase angle (radians)", "زاوية العدد المركب"),
    "isnan": (np.isnan, "True for NaN elements", "التحقق من القيم غير العددية NaN"),
    "isinf": (np.isinf, "True for infinite elements", "التحقق من القيم اللانهائية"),
    "isfinite": (np.isfinite, "True for finite elements", "التحقق من القيم المحدودة"),
    "deg2rad": (np.deg2rad, "Degrees to radians", "تحويل درجات إلى راديان"),
    "rad2deg": (np.rad2deg, "Radians to degrees", "تحويل راديان إلى درجات"),
    "mag2db": (lambda x: 20 * np.log10(x), "Magnitude to decibels (20 log10)", "تحويل المقدار إلى ديسيبل"),
    "db2mag": (lambda x: 10 ** (x / 20), "Decibels to magnitude", "تحويل الديسيبل إلى مقدار"),
    "gamma": (lambda x: __import__("scipy.special", fromlist=["gamma"]).gamma(x), "Gamma function", "دالة كاما"),
}


def _make_elementwise(name, fn):
    def f(ip, args, nargout):
        nargs(args, 1, 1, name)
        x = num_arg(args[0])
        if x.dtype == bool:
            x = x.astype(float)
        with np.errstate(all="ignore"):
            return arr(fn(x))
    return f


for _name, (_fn, _en, _ar) in _ELEMENTWISE.items():
    builtin(_name, sig=f"{_name}(x)", en=_en, ar=_ar, cat="Math")(_make_elementwise(_name, _fn))


@builtin("round", sig="round(x) / round(x, n)", en="Round to nearest integer (or n decimals)",
         ar="التقريب لأقرب عدد صحيح", cat="Math")
def _round(ip, args, nargout):
    nargs(args, 1, 2, "round")
    x = num_arg(args[0])
    n = int_arg(args[1]) if len(args) > 1 else 0
    # MATLAB rounds half away from zero
    f = 10.0 ** n
    if np.iscomplexobj(x):
        return arr((np.sign(x.real) * np.floor(np.abs(x.real) * f + 0.5) +
                    1j * np.sign(x.imag) * np.floor(np.abs(x.imag) * f + 0.5)) / f)
    return arr(np.sign(x) * np.floor(np.abs(x) * f + 0.5) / f)


@builtin("atan2", sig="atan2(y, x)", en="Four-quadrant inverse tangent", ar="معكوس الظل رباعي الأرباع", cat="Math")
def _atan2(ip, args, nargout):
    nargs(args, 2, 2, "atan2")
    return arr(np.arctan2(num_arg(args[0]), num_arg(args[1])))


@builtin("mod", sig="mod(a, m)", en="Modulus after division (sign of m)", ar="باقي القسمة", cat="Math")
def _mod(ip, args, nargout):
    nargs(args, 2, 2, "mod")
    a, m = num_arg(args[0]), num_arg(args[1])
    with np.errstate(all="ignore"):
        return arr(np.where(m == 0, a, np.mod(a, np.where(m == 0, 1, m))))


@builtin("rem", sig="rem(a, b)", en="Remainder after division (sign of a)", ar="باقي القسمة (بإشارة المقسوم)", cat="Math")
def _rem(ip, args, nargout):
    nargs(args, 2, 2, "rem")
    return arr(np.fmod(num_arg(args[0]), num_arg(args[1])))


@builtin("hypot", sig="hypot(a, b)", en="sqrt(a^2 + b^2)", ar="طول الوتر", cat="Math")
def _hypot(ip, args, nargout):
    return arr(np.hypot(num_arg(args[0]), num_arg(args[1])))


@builtin("nthroot", sig="nthroot(x, n)", en="Real n-th root", ar="الجذر النوني الحقيقي", cat="Math")
def _nthroot(ip, args, nargout):
    x, n = num_arg(args[0]).astype(float), num_arg(args[1]).astype(float)
    return arr(np.sign(x) * np.abs(x) ** (1.0 / n))


@builtin("power", sig="power(a, b)", en="Element-wise power a.^b", ar="الرفع لقوة عنصر بعنصر", cat="Math")
def _powerfn(ip, args, nargout):
    from ..interpreter import binary_op
    return binary_op(".^", args[0], args[1])


@builtin("factorial", sig="factorial(n)", en="Factorial n!", ar="المضروب", cat="Math")
def _factorial(ip, args, nargout):
    from scipy.special import factorial
    return arr(factorial(num_arg(args[0]), exact=False))


# ---------------------------------------------------------------------------
# reductions & queries
# ---------------------------------------------------------------------------

def _reduction(name, fn, en, ar):
    def f(ip, args, nargout):
        nargs(args, 1, 2, name)
        a = num_arg(args[0])
        if a.dtype == bool:
            a = a.astype(float)
        if a.size == 0:
            return arr({"sum": 0.0, "prod": 1.0}.get(name, np.nan))
        dim = int_arg(args[1]) - 1 if len(args) > 1 else first_dim(a)
        return arr(fn(a, axis=dim, keepdims=True))
    builtin(name, sig=f"{name}(x) / {name}(x, dim)", en=en, ar=ar, cat="Data")(f)


_reduction("sum", np.sum, "Sum of elements", "مجموع العناصر")
_reduction("prod", np.prod, "Product of elements", "حاصل ضرب العناصر")
_reduction("mean", np.mean, "Average value", "المتوسط الحسابي")
_reduction("median", np.median, "Median value", "الوسيط")


@builtin("cumsum", sig="cumsum(x)", en="Cumulative sum", ar="المجموع التراكمي", cat="Data")
def _cumsum(ip, args, nargout):
    a = num_arg(args[0])
    dim = int_arg(args[1]) - 1 if len(args) > 1 else first_dim(a)
    return arr(np.cumsum(a, axis=dim))


@builtin("cumprod", sig="cumprod(x)", en="Cumulative product", ar="الضرب التراكمي", cat="Data")
def _cumprod(ip, args, nargout):
    a = num_arg(args[0])
    dim = int_arg(args[1]) - 1 if len(args) > 1 else first_dim(a)
    return arr(np.cumprod(a, axis=dim))


@builtin("std", sig="std(x)", en="Standard deviation", ar="الانحراف المعياري", cat="Data")
def _std(ip, args, nargout):
    a = num_arg(args[0]).astype(float)
    dim = first_dim(a)
    return arr(np.std(a, axis=dim, ddof=1 if a.shape[dim] > 1 else 0, keepdims=True))


@builtin("var", sig="var(x)", en="Variance", ar="التباين", cat="Data")
def _var(ip, args, nargout):
    a = num_arg(args[0]).astype(float)
    dim = first_dim(a)
    return arr(np.var(a, axis=dim, ddof=1 if a.shape[dim] > 1 else 0, keepdims=True))


def _minmax(name, pick, argpick):
    def f(ip, args, nargout):
        nargs(args, 1, 3, name)
        a = num_arg(args[0])
        if len(args) >= 2 and not (isinstance(args[1], np.ndarray) and args[1].size == 0):
            b = num_arg(args[1])
            return arr(pick(a, b))
        if a.size == 0:
            return Multi([np.zeros((0, 0)), np.zeros((0, 0))])
        dim = int_arg(args[2]) - 1 if len(args) == 3 else first_dim(a)
        key = np.abs(a) if np.iscomplexobj(a) else a
        idx = argpick(np.where(np.isnan(key), -np.inf if argpick is np.nanargmax else np.inf, key)
                      if key.dtype.kind == "f" else key, axis=dim)
        idx = np.expand_dims(idx, dim)
        vals = np.take_along_axis(a, idx, axis=dim)
        return Multi([arr(vals), arr(idx + 1.0)])
    return f


builtin("max", sig="max(x) / [m, i] = max(x) / max(a, b)", en="Largest element",
        ar="أكبر عنصر", cat="Data")(_minmax("max", np.fmax, np.nanargmax))
builtin("min", sig="min(x) / [m, i] = min(x) / min(a, b)", en="Smallest element",
        ar="أصغر عنصر", cat="Data")(_minmax("min", np.fmin, np.nanargmin))


@builtin("length", sig="length(x)", en="Length of largest dimension", ar="طول المتجه", cat="Data")
def _length(ip, args, nargout):
    s = size_of(args[0])
    return arr(0 if 0 in s else max(s))


@builtin("numel", sig="numel(x)", en="Number of elements", ar="عدد العناصر", cat="Data")
def _numel(ip, args, nargout):
    s = size_of(args[0])
    return arr(s[0] * s[1])


@builtin("size", sig="size(A) / size(A, dim) / [r, c] = size(A)", en="Array dimensions",
         ar="أبعاد المصفوفة", cat="Data")
def _size(ip, args, nargout):
    nargs(args, 1, 2, "size")
    s = size_of(args[0])
    if len(args) == 2:
        d = int_arg(args[1])
        return arr(s[d - 1] if d <= 2 else 1)
    if nargout >= 2:
        return Multi([arr(s[0]), arr(s[1])] + [arr(1)] * (nargout - 2))
    return arr([float(s[0]), float(s[1])])


@builtin("ndims", sig="ndims(A)", en="Number of dimensions", ar="عدد الأبعاد", cat="Data")
def _ndims(ip, args, nargout):
    return arr(2)


def _predicate(name, fn, en, ar):
    builtin(name, sig=f"{name}(x)", en=en, ar=ar, cat="Data")(
        lambda ip, args, nargout: np.array([[bool(fn(args[0]))]]))


_predicate("isempty", lambda v: 0 in size_of(v), "True if empty", "التحقق من كون المصفوفة فارغة")
_predicate("isscalar", lambda v: size_of(v) == (1, 1), "True if scalar", "التحقق من كون القيمة عدداً مفرداً")
_predicate("isvector", lambda v: 1 in size_of(v) and max(size_of(v)) >= 1, "True if vector", "التحقق من كون القيمة متجهاً")
_predicate("isrow", lambda v: size_of(v)[0] == 1, "True if row vector", "التحقق من كون القيمة متجهاً صفياً")
_predicate("iscolumn", lambda v: size_of(v)[1] == 1, "True if column vector", "التحقق من كون القيمة متجهاً عمودياً")
_predicate("ischar", lambda v: isinstance(v, str), "True if character array", "التحقق من كون القيمة نصاً")
_predicate("isnumeric", lambda v: isinstance(v, np.ndarray) and v.dtype != bool, "True if numeric", "التحقق من كون القيمة رقمية")
_predicate("islogical", lambda v: isinstance(v, np.ndarray) and v.dtype == bool, "True if logical", "التحقق من كون القيمة منطقية")
_predicate("isstruct", lambda v: isinstance(v, Struct), "True if struct", "التحقق من كون القيمة بنية بيانات (struct)")
_predicate("iscell", lambda v: isinstance(v, Cell), "True if cell array", "التحقق من كون القيمة مصفوفة خلايا (cell)")
_predicate("isreal", lambda v: not (isinstance(v, np.ndarray) and np.iscomplexobj(v)), "True if real", "التحقق من كون القيمة حقيقية")
_predicate("istf", lambda v: isinstance(v, TransferFunction), "True if transfer function", "التحقق من كون القيمة دالة تحويل")
_predicate("is_function_handle", lambda v: isinstance(v, FunctionHandle), "True if function handle", "التحقق من كون القيمة مقبض دالة")


@builtin("any", sig="any(x)", en="True if any element is nonzero", ar="التحقق من وجود عنصر غير صفري", cat="Data")
def _any(ip, args, nargout):
    a = num_arg(args[0])
    if a.size == 0:
        return np.array([[False]])
    if min(a.shape) == 1:
        return np.array([[bool(np.any(a != 0))]])
    return arr(np.any(a != 0, axis=0, keepdims=True))


@builtin("all", sig="all(x)", en="True if all elements are nonzero", ar="التحقق من أن جميع العناصر غير صفرية", cat="Data")
def _all(ip, args, nargout):
    a = num_arg(args[0])
    if a.size == 0:
        return np.array([[True]])
    if min(a.shape) == 1:
        return np.array([[bool(np.all(a != 0))]])
    return arr(np.all(a != 0, axis=0, keepdims=True))


@builtin("find", sig="find(x) / find(x, n)", en="Indices of nonzero elements", ar="مواقع العناصر غير الصفرية", cat="Data")
def _find(ip, args, nargout):
    a = num_arg(args[0])
    flat = a.ravel(order="F")
    idx = np.flatnonzero(flat != 0)
    if len(args) > 1:
        idx = idx[:int_arg(args[1])]
    if nargout >= 2:
        r, c = np.unravel_index(idx, a.shape, order="F")
        out = [col(r + 1.0), col(c + 1.0)]
        if a.shape[0] == 1:
            out = [row(r + 1.0), row(c + 1.0)]
        return Multi(out)
    res = idx + 1.0
    return row(res) if a.shape[0] == 1 else col(res)


@builtin("sort", sig="sort(x) / sort(x, 'descend') / [s, i] = sort(x)", en="Sort elements",
         ar="ترتيب العناصر", cat="Data")
def _sort(ip, args, nargout):
    a = num_arg(args[0])
    desc = len(args) > 1 and isinstance(args[-1], str) and args[-1].lower() == "descend"
    dim = first_dim(a)
    key = np.abs(a) if np.iscomplexobj(a) else a
    idx = np.argsort(-key if desc else key, axis=dim, kind="stable")
    vals = np.take_along_axis(a, idx, axis=dim)
    return Multi([arr(vals), arr(idx + 1.0)])


@builtin("sortrows", sig="sortrows(A)  |  sortrows(A, col)  |  [B, i] = sortrows(A, -col)",
         en="Sort the rows of a matrix by a column (negative column = descending)",
         ar="ترتيب صفوف المصفوفة حسب عمود", cat="Data")
def _sortrows(ip, args, nargout):
    a = num_arg(args[0])
    cols = [int(c) for c in vector(args[1]).real] if len(args) > 1 else list(range(1, a.shape[1] + 1))
    keys = []
    for c in reversed(cols):
        k = np.real(a[:, abs(c) - 1])
        keys.append(-k if c < 0 else k)
    idx = np.lexsort(keys) if keys else np.arange(a.shape[0])
    return Multi([a[idx, :], col(idx + 1.0)])


@builtin("unique", sig="unique(x)", en="Unique sorted values", ar="القيم الفريدة", cat="Data")
def _unique(ip, args, nargout):
    a = num_arg(args[0])
    u = np.unique(a.ravel())
    return row(u) if a.shape[0] == 1 else col(u)


@builtin("fliplr", sig="fliplr(A)", en="Flip left-right", ar="قلب المصفوفة أفقياً", cat="Matrix")
def _fliplr(ip, args, nargout):
    if isinstance(args[0], str):
        return args[0][::-1]
    return arr(np.fliplr(num_arg(args[0])))


@builtin("flipud", sig="flipud(A)", en="Flip up-down", ar="قلب المصفوفة عمودياً", cat="Matrix")
def _flipud(ip, args, nargout):
    return arr(np.flipud(num_arg(args[0])))


@builtin("flip", sig="flip(A)", en="Flip order of elements", ar="عكس ترتيب العناصر", cat="Matrix")
def _flip(ip, args, nargout):
    if isinstance(args[0], str):
        return args[0][::-1]
    a = num_arg(args[0])
    return arr(np.flip(a, axis=first_dim(a)))


@builtin("diff", sig="diff(x)", en="Differences between adjacent elements", ar="الفروق بين العناصر المتتالية", cat="Data")
def _diff(ip, args, nargout):
    a = num_arg(args[0])
    n = int_arg(args[1]) if len(args) > 1 else 1
    return arr(np.diff(a, n=n, axis=first_dim(a)))


@builtin("trapz", sig="trapz(y) / trapz(x, y)", en="Trapezoidal numerical integration",
         ar="التكامل العددي بطريقة شبه المنحرف", cat="Data")
def _trapz(ip, args, nargout):
    if len(args) == 1:
        return arr(np.trapezoid(vector(args[0])))
    return arr(np.trapezoid(vector(args[1]), vector(args[0])))


@builtin("dot", sig="dot(a, b)", en="Dot product", ar="الضرب النقطي", cat="Matrix")
def _dot(ip, args, nargout):
    return arr(np.vdot(vector(args[0]), vector(args[1])))


@builtin("cross", sig="cross(a, b)", en="Cross product", ar="الضرب الاتجاهي", cat="Matrix")
def _cross(ip, args, nargout):
    a = num_arg(args[0])
    r = np.cross(vector(args[0]), vector(args[1]))
    return row(r) if a.shape[0] == 1 else col(r)


@builtin("norm", sig="norm(x) / norm(x, p)", en="Vector or matrix norm", ar="المعيار (الطول)", cat="Matrix")
def _norm(ip, args, nargout):
    a = num_arg(args[0])
    p = 2
    if len(args) > 1:
        p = args[1] if isinstance(args[1], str) else scalar(args[1])
        if isinstance(p, str):
            p = {"fro": "fro", "inf": np.inf, "Inf": np.inf}[p]
    if min(a.shape) == 1:
        return arr(np.linalg.norm(a.ravel(), p if p != "fro" else 2))
    return arr(np.linalg.norm(a, p))


# ---------------------------------------------------------------------------
# constructors
# ---------------------------------------------------------------------------

def _shape_args(args, name):
    dims = [a for a in args if not isinstance(a, str)]
    if not dims:
        return (1, 1)
    # like MATLAB, negative sizes give an empty matrix
    if len(dims) == 1:
        d = to_array(dims[0]).ravel()
        if d.size == 0:
            return (0, 0)
        if d.size == 1:
            n = max(int(np.real(d[0])), 0)
            return (n, n)
        return (max(int(np.real(d[0])), 0), max(int(np.real(d[1])), 0))
    return (max(int_arg(dims[0]), 0), max(int_arg(dims[1]), 0))


@builtin("zeros", sig="zeros(n) / zeros(m, n)", en="Matrix of zeros", ar="مصفوفة أصفار", cat="Matrix")
def _zeros(ip, args, nargout):
    return np.zeros(_shape_args(args, "zeros"))


@builtin("ones", sig="ones(n) / ones(m, n)", en="Matrix of ones", ar="مصفوفة آحاد", cat="Matrix")
def _ones(ip, args, nargout):
    return np.ones(_shape_args(args, "ones"))


@builtin("eye", sig="eye(n)", en="Identity matrix", ar="مصفوفة الوحدة", cat="Matrix")
def _eye(ip, args, nargout):
    r, c = _shape_args(args, "eye")
    return np.eye(r, c)


@builtin("rand", sig="rand(n) / rand(m, n)", en="Uniform random numbers in (0,1)", ar="أرقام عشوائية منتظمة", cat="Matrix")
def _rand(ip, args, nargout):
    return np.random.rand(*_shape_args(args, "rand"))


@builtin("randn", sig="randn(n) / randn(m, n)", en="Normally distributed random numbers", ar="أرقام عشوائية طبيعية", cat="Matrix")
def _randn(ip, args, nargout):
    return np.random.randn(*_shape_args(args, "randn"))


@builtin("randi", sig="randi(imax, m, n)", en="Random integers", ar="أعداد صحيحة عشوائية", cat="Matrix")
def _randi(ip, args, nargout):
    lim = vector(args[0])
    lo, hi = (1, int(lim[0])) if lim.size == 1 else (int(lim[0]), int(lim[1]))
    shape = _shape_args(args[1:], "randi") if len(args) > 1 else (1, 1)
    return np.random.randint(lo, hi + 1, size=shape).astype(float)


@builtin("rng", sig="rng(seed)", en="Seed the random number generator", ar="تثبيت مولد الأرقام العشوائية", cat="Matrix")
def _rng(ip, args, nargout):
    if args and not isinstance(args[0], str):
        np.random.seed(int_arg(args[0]))


@builtin("linspace", sig="linspace(a, b, n)", en="Linearly spaced vector", ar="متجه بقيم متساوية التباعد", cat="Matrix")
def _linspace(ip, args, nargout):
    nargs(args, 2, 3, "linspace")
    n = int_arg(args[2]) if len(args) > 2 else 100
    return row(np.linspace(scalar(args[0]), scalar(args[1]), n))


@builtin("logspace", sig="logspace(a, b, n)", en="Logarithmically spaced vector (10^a to 10^b)",
         ar="متجه بتباعد لوغاريتمي", cat="Matrix")
def _logspace(ip, args, nargout):
    nargs(args, 2, 3, "logspace")
    n = int_arg(args[2]) if len(args) > 2 else 50
    return row(np.logspace(scalar(args[0]), scalar(args[1]), n))


@builtin("magic", sig="magic(n)", en="Magic square", ar="المربع السحري", cat="Matrix")
def _magic(ip, args, nargout):
    n = int_arg(args[0])
    if n < 1:
        return np.zeros((0, 0))
    if n == 2:
        return np.array([[4.0, 3.0], [1.0, 2.0]])
    M = np.zeros((n, n))
    if n % 2 == 1:
        i, j = 0, n // 2
        for k in range(1, n * n + 1):
            M[i, j] = k
            i2, j2 = (i - 1) % n, (j + 1) % n
            if M[i2, j2]:
                i2, j2 = (i + 1) % n, j
            i, j = i2, j2
        return M
    if n % 4 == 0:
        A_ = np.arange(1, n * n + 1).reshape(n, n).astype(float)
        I, J = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        mask = ((I % 4) // 2) == ((J % 4) // 2)
        A_[mask] = n * n + 1 - A_[mask]
        return A_
    # singly even (LUX method)
    m = n // 2
    sub = _magic(ip, [np.array([[m]])], 1)
    M = np.block([[sub, sub + 2 * m * m], [sub + 3 * m * m, sub + m * m]])
    k = (n - 2) // 4
    cols = list(range(k)) + list(range(n - k + 1, n))
    for c in cols:
        M[[*range(m)], c], M[[*range(m, n)], c] = M[[*range(m, n)], c].copy(), M[[*range(m)], c].copy()
    for c in (0, k):
        M[k, c], M[k + m, c] = M[k + m, c], M[k, c]
    return M


@builtin("diag", sig="diag(v) / diag(A)", en="Diagonal matrix or diagonal of a matrix",
         ar="القطر الرئيسي", cat="Matrix")
def _diag(ip, args, nargout):
    a = num_arg(args[0])
    k = int_arg(args[1]) if len(args) > 1 else 0
    if min(a.shape) == 1:
        return np.diag(a.ravel(), k)
    return col(np.diag(a, k))


@builtin("repmat", sig="repmat(A, m, n)", en="Replicate and tile an array", ar="تكرار المصفوفة", cat="Matrix")
def _repmat(ip, args, nargout):
    a = num_arg(args[0])
    m, n = _shape_args(args[1:], "repmat")
    return np.tile(a, (m, n))


@builtin("reshape", sig="reshape(A, m, n)", en="Reshape array", ar="إعادة تشكيل المصفوفة", cat="Matrix")
def _reshape(ip, args, nargout):
    a = num_arg(args[0])
    if len(args) == 2:
        m, n = (int(x) for x in vector(args[1])[:2])
    else:
        dims = [None if (isinstance(x, np.ndarray) and x.size == 0) else int_arg(x) for x in args[1:3]]
        m, n = dims
        if m is None:
            m = a.size // n
        if n is None:
            n = a.size // m
    if m * n != a.size:
        raise MatlabError("Number of elements must not change. Use [] as one of the size "
                          "inputs to automatically calculate the appropriate size.")
    return a.ravel(order="F").reshape((m, n), order="F")


@builtin("meshgrid", sig="[X, Y] = meshgrid(x, y)", en="2-D grid coordinates", ar="شبكة إحداثيات ثنائية", cat="Matrix")
def _meshgrid(ip, args, nargout):
    x = vector(args[0])
    y = vector(args[1]) if len(args) > 1 else x
    X, Y = np.meshgrid(x, y)
    return Multi([X, Y])


@builtin("kron", sig="kron(A, B)", en="Kronecker product", ar="ضرب كرونكر", cat="Matrix")
def _kron(ip, args, nargout):
    return np.kron(num_arg(args[0]), num_arg(args[1]))


# ---------------------------------------------------------------------------
# linear algebra
# ---------------------------------------------------------------------------

def _square(a, name):
    if a.shape[0] != a.shape[1]:
        raise MatlabError(f"Matrix must be square for '{name}'.")


@builtin("inv", sig="inv(A)", en="Matrix inverse", ar="معكوس المصفوفة", cat="Linear algebra")
def _inv(ip, args, nargout):
    a = num_arg(args[0])
    _square(a, "inv")
    if np.linalg.matrix_rank(a) < a.shape[0]:
        ip.write("Warning: Matrix is singular to working precision.\n")
        return np.full(a.shape, np.inf)
    return arr(np.linalg.inv(a))


@builtin("pinv", sig="pinv(A)", en="Pseudo-inverse", ar="المعكوس الزائف للمصفوفة", cat="Linear algebra")
def _pinv(ip, args, nargout):
    return arr(np.linalg.pinv(num_arg(args[0])))


@builtin("det", sig="det(A)", en="Determinant", ar="المحدد", cat="Linear algebra")
def _det(ip, args, nargout):
    a = num_arg(args[0])
    _square(a, "det")
    d = np.linalg.det(a)
    if abs(d) < 1e-10 * max(1, np.max(np.abs(a))) ** a.shape[0]:
        d = 0.0
    return arr(d)


@builtin("rank", sig="rank(A)", en="Matrix rank", ar="رتبة المصفوفة", cat="Linear algebra")
def _rank(ip, args, nargout):
    return arr(float(np.linalg.matrix_rank(num_arg(args[0]))))


@builtin("trace", sig="trace(A)", en="Sum of diagonal elements", ar="أثر المصفوفة", cat="Linear algebra")
def _trace(ip, args, nargout):
    return arr(np.trace(num_arg(args[0])))


@builtin("transpose", sig="transpose(A)", en="Transpose", ar="المنقول", cat="Linear algebra")
def _transpose(ip, args, nargout):
    return num_arg(args[0]).T


@builtin("eig", sig="eig(A) / [V, D] = eig(A)", en="Eigenvalues and eigenvectors",
         ar="القيم الذاتية والمتجهات الذاتية", cat="Linear algebra")
def _eig(ip, args, nargout):
    a = num_arg(args[0])
    _square(a, "eig")
    w, v = np.linalg.eig(a)
    order = np.lexsort((w.imag, w.real))
    w, v = w[order], v[:, order]
    if nargout >= 2:
        return Multi([arr(v), arr(np.diag(w))])
    return simplify(col(w))


@builtin("expm", sig="expm(A)", en="Matrix exponential e^A", ar="الأسية المصفوفية", cat="Linear algebra")
def _expm(ip, args, nargout):
    from scipy.linalg import expm
    return arr(expm(num_arg(args[0])))


@builtin("rref", sig="rref(A)", en="Reduced row echelon form", ar="الصيغة الدرجية المختزلة", cat="Linear algebra")
def _rref(ip, args, nargout):
    A_ = num_arg(args[0]).astype(float).copy()
    rows, cols = A_.shape
    r = 0
    tol = max(rows, cols) * np.finfo(float).eps * (np.linalg.norm(A_, np.inf) if A_.size else 0)
    for c in range(cols):
        if r >= rows:
            break
        p = r + int(np.argmax(np.abs(A_[r:, c])))
        if abs(A_[p, c]) <= tol:
            A_[r:, c] = 0
            continue
        A_[[r, p]] = A_[[p, r]]
        A_[r] /= A_[r, c]
        for k in range(rows):
            if k != r:
                A_[k] -= A_[k, c] * A_[r]
        r += 1
    return A_


# ---------------------------------------------------------------------------
# polynomials
# ---------------------------------------------------------------------------

@builtin("roots", sig="roots(p)", en="Polynomial roots", ar="جذور كثيرة الحدود", cat="Polynomials")
def _roots(ip, args, nargout):
    from ...control.tf import roots
    p = vector(args[0])
    r = roots(p)
    return simplify(col(r)) if r.size else np.zeros((0, 1))


@builtin("poly", sig="poly(r) / poly(A)", en="Polynomial from roots (or characteristic polynomial)",
         ar="كثيرة حدود من الجذور", cat="Polynomials")
def _poly(ip, args, nargout):
    a = num_arg(args[0])
    if a.shape[0] == a.shape[1] and a.shape[0] > 1:
        return arr(np.real_if_close(np.poly(a)))
    p = np.poly(a.ravel()) if a.size else np.array([1.0])
    return arr(np.real_if_close(p, tol=1000))


@builtin("polyval", sig="polyval(p, x)", en="Evaluate polynomial", ar="حساب قيمة كثيرة الحدود", cat="Polynomials")
def _polyval(ip, args, nargout):
    p = vector(args[0])
    x = num_arg(args[1])
    return arr(np.polyval(p, x))


@builtin("polyfit", sig="polyfit(x, y, n)", en="Polynomial curve fitting", ar="ملاءمة منحنى بكثيرة حدود", cat="Polynomials")
def _polyfit(ip, args, nargout):
    return row(np.polyfit(vector(args[0]), vector(args[1]), int_arg(args[2])))


@builtin("conv", sig="conv(a, b)", en="Polynomial multiplication (convolution)",
         ar="ضرب كثيرات الحدود (الالتفاف)", cat="Polynomials")
def _conv(ip, args, nargout):
    a = num_arg(args[0])
    r = np.convolve(vector(args[0]), vector(args[1]))
    return col(r) if a.shape[1] == 1 and a.shape[0] > 1 else row(r)


@builtin("deconv", sig="[q, r] = deconv(a, b)", en="Polynomial division", ar="قسمة كثيرات الحدود", cat="Polynomials")
def _deconv(ip, args, nargout):
    a, b = vector(args[0]), vector(args[1])
    q, r = np.polydiv(a, b)
    r_full = np.concatenate([np.zeros(len(a) - len(r)), r])
    return Multi([row(q), row(r_full)])


@builtin("polyder", sig="polyder(p)", en="Polynomial derivative", ar="مشتقة كثيرة الحدود", cat="Polynomials")
def _polyder(ip, args, nargout):
    if len(args) == 2:
        return row(np.polyder(np.polymul(vector(args[0]), vector(args[1]))))
    return row(np.polyder(vector(args[0])))


@builtin("polyint", sig="polyint(p)", en="Polynomial integral", ar="تكامل كثيرة الحدود", cat="Polynomials")
def _polyint(ip, args, nargout):
    k = scalar(args[1]) if len(args) > 1 else 0
    return row(np.polyint(vector(args[0]), k=k))


@builtin("residue", sig="[r, p, k] = residue(b, a)", en="Partial fraction expansion",
         ar="تفكيك الكسور الجزئية", cat="Polynomials")
def _residue(ip, args, nargout):
    from scipy.signal import residue
    r, p, k = residue(vector(args[0]), vector(args[1]))
    return Multi([simplify(col(r)), simplify(col(p)), row(k) if len(k) else np.zeros((0, 0))])


# ---------------------------------------------------------------------------
# strings and output
# ---------------------------------------------------------------------------

_SPEC = re.compile(r"%(?P<flags>[-+ #0]*)(?P<width>\*|\d+)?(?:\.(?P<prec>\*|\d+))?(?P<conv>[diouxXeEfgGcs])")


def _unescape(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            mapping = {"n": "\n", "t": "\t", "\\": "\\", "r": "\r", "a": "\a", "'": "'", '"': '"'}
            if n in mapping:
                out.append(mapping[n])
                i += 2
                continue
        out.append(c)
        i += 1
    return "".join(out)


def _fmt_one(spec, value):
    flags, width, prec, conv = spec
    w = width or ""
    p = f".{prec}" if prec is not None else ""
    if conv == "s":
        if not isinstance(value, str):
            v = value
            if isinstance(v, float) and v == int(v):
                value = str(int(v))
            else:
                value = f"{v:g}" if isinstance(v, (int, float)) else str(v)
        return f"%{flags}{w}{p}s" % value
    if isinstance(value, str):
        value = float(ord(value[0])) if len(value) == 1 else value
        if isinstance(value, str):
            return f"%{flags}{w}s" % value
    if isinstance(value, complex):
        value = value.real
    if conv == "c":
        return chr(int(value))
    if conv in "diuoxX":
        if np.isnan(value) or np.isinf(value):
            return f"%{flags}{w}s" % ("NaN" if np.isnan(value) else ("Inf" if value > 0 else "-Inf"))
        if value != int(value):
            return f"%{flags}{w}e" % value
        c = "d" if conv in "diu" else conv
        return f"%{flags}{w}{c}" % int(value)
    if np.isnan(value) or np.isinf(value):
        return f"%{flags}{w}s" % ("NaN" if np.isnan(value) else ("Inf" if value > 0 else "-Inf"))
    return f"%{flags}{w}{p}{conv}" % value


def mformat(fmt, values):
    """MATLAB sprintf semantics: the format is reused until values run out."""
    fmt = _unescape(fmt)
    items = []
    for v in values:
        if isinstance(v, str):
            items.append(v)
        elif isinstance(v, TransferFunction):
            items.append(v.to_str())
        elif isinstance(v, (Cell, Struct, FunctionHandle)):
            raise MatlabError("Only numeric and char arguments are supported by sprintf/fprintf.")
        else:
            a = to_array(v)
            for x in a.ravel(order="F"):
                if a.dtype == bool:
                    x = float(x)
                items.append(complex(x) if np.iscomplexobj(a) else float(x))
    specs = list(_SPEC.finditer(fmt))
    if not specs:
        return fmt.replace("%%", "%")
    out = []
    k = 0
    first = True
    while first or k < len(items):
        first = False
        pos = 0
        for m in specs:
            out.append(fmt[pos:m.start()].replace("%%", "%"))
            if k >= len(items):
                if items or m is not specs[0]:
                    return "".join(out)
                return "".join(out)
            spec = (m.group("flags"), m.group("width"), m.group("prec"), m.group("conv"))
            if spec[1] == "*":
                spec = (spec[0], str(int(items[k])), spec[2], spec[3])
                k += 1
            if spec[2] == "*":
                spec = (spec[0], spec[1], str(int(items[k])), spec[3])
                k += 1
            out.append(_fmt_one(spec, items[k]))
            k += 1
            pos = m.end()
        out.append(fmt[pos:].replace("%%", "%"))
    return "".join(out)


@builtin("sprintf", sig="sprintf(fmt, ...)", en="Format data into a string", ar="تنسيق نص", cat="Strings")
def _sprintf(ip, args, nargout):
    nargs(args, 1, None, "sprintf")
    return mformat(str_arg(args[0], "format"), args[1:])


@builtin("fprintf", sig="fprintf(fmt, ...)", en="Print formatted text", ar="طباعة نص منسق", cat="Strings")
def _fprintf(ip, args, nargout):
    nargs(args, 1, None, "fprintf")
    if not isinstance(args[0], str) and len(args) > 1:
        args = args[1:]   # fprintf(1, ...) -> stdout
    ip.write(mformat(str_arg(args[0], "format"), args[1:]))


def display_text(v, long=False):
    if isinstance(v, str):
        return v + "\n"
    if isinstance(v, TransferFunction):
        return v.to_str() + "\n"
    if isinstance(v, (Struct, Cell, FunctionHandle)):
        return "\n".join(format_value("", v, long).split("\n")[2:]) + "\n"
    a = to_array(v)
    if a.size == 0:
        return ""
    return format_matrix(a, long) + "\n"


@builtin("disp", sig="disp(x)", en="Display value without the variable name", ar="عرض قيمة", cat="Strings")
def _disp(ip, args, nargout):
    nargs(args, 1, 1, "disp")
    ip.write(display_text(args[0], ip.format_long))


@builtin("display", sig="display(x)", en="Display value", ar="عرض قيمة", cat="Strings")
def _display(ip, args, nargout):
    ip.write(format_value("ans", args[0], ip.format_long))


def num2str_value(v, prec=None):
    if isinstance(v, str):
        return v
    a = to_array(v)
    if a.size == 0:
        return ""

    def one(x):
        if isinstance(x, (complex, np.complexfloating)) and x.imag != 0:
            im = one(abs(x.imag))
            return f"{one(x.real)}{'-' if x.imag < 0 else '+'}{im}i"
        x = float(np.real(x))
        if np.isnan(x):
            return "NaN"
        if np.isinf(x):
            return "Inf" if x > 0 else "-Inf"
        if prec is not None:
            return f"{x:.{prec}g}"
        if x == int(x) and abs(x) < 1e15:
            return str(int(x))
        digits = max(int(np.floor(np.log10(abs(x)))), 0) + 5 if x != 0 else 5
        return f"{x:.{digits}g}"

    rows = []
    for r in a:
        rows.append("  ".join(one(x) for x in r))
    return "\n".join(rows)


@builtin("num2str", sig="num2str(x) / num2str(x, precision)", en="Convert number to string",
         ar="تحويل رقم إلى نص", cat="Strings")
def _num2str(ip, args, nargout):
    nargs(args, 1, 2, "num2str")
    if len(args) == 2:
        if isinstance(args[1], str):
            return mformat(args[1], [args[0]])
        return num2str_value(args[0], int_arg(args[1]))
    return num2str_value(args[0])


@builtin("int2str", sig="int2str(x)", en="Round and convert to string", ar="تحويل عدد صحيح إلى نص", cat="Strings")
def _int2str(ip, args, nargout):
    return num2str_value(np.round(num_arg(args[0])))


@builtin("str2num", "str2double", sig="str2double(s)", en="Convert string to number",
         ar="تحويل نص إلى رقم", cat="Strings")
def _str2double(ip, args, nargout):
    s = args[0]
    if not isinstance(s, str):
        return np.array([[np.nan]])
    try:
        return arr(float(s.strip()))
    except ValueError:
        try:
            return arr(complex(s.strip().replace("i", "j")))
        except ValueError:
            return np.array([[np.nan]])


@builtin("mat2str", sig="mat2str(A)", en="Matrix to string with brackets", ar="تحويل مصفوفة إلى نص", cat="Strings")
def _mat2str(ip, args, nargout):
    a = num_arg(args[0])
    prec = int_arg(args[1]) if len(args) > 1 else 15

    def one(x):
        if isinstance(x, (complex, np.complexfloating)):
            return f"{x.real + 0.0:.{prec}g}{x.imag + 0.0:+.{prec}g}i"
        if a.dtype == bool:
            return "true" if x else "false"
        return f"{float(x):.{prec}g}"
    if a.size == 1:
        return one(a.ravel()[0])
    return "[" + ";".join(" ".join(one(x) for x in r) for r in a) + "]"


@builtin("strcat", sig="strcat(s1, s2, ...)", en="Concatenate strings", ar="دمج النصوص", cat="Strings")
def _strcat(ip, args, nargout):
    return "".join(a.rstrip() if isinstance(a, str) else num2str_value(a) for a in args)


@builtin("strcmp", sig="strcmp(a, b)", en="Compare strings", ar="مقارنة نصين", cat="Strings")
def _strcmp(ip, args, nargout):
    return np.array([[isinstance(args[0], str) and isinstance(args[1], str) and args[0] == args[1]]])


@builtin("strcmpi", sig="strcmpi(a, b)", en="Compare strings ignoring case", ar="مقارنة نصين دون مراعاة حالة الأحرف", cat="Strings")
def _strcmpi(ip, args, nargout):
    return np.array([[isinstance(args[0], str) and isinstance(args[1], str)
                      and args[0].lower() == args[1].lower()]])


@builtin("upper", sig="upper(s)", en="Uppercase", ar="تحويل النص إلى أحرف كبيرة", cat="Strings")
def _upper(ip, args, nargout):
    return str_arg(args[0]).upper()


@builtin("lower", sig="lower(s)", en="Lowercase", ar="تحويل النص إلى أحرف صغيرة", cat="Strings")
def _lower(ip, args, nargout):
    return str_arg(args[0]).lower()


@builtin("strrep", sig="strrep(s, old, new)", en="Replace substring", ar="استبدال نص", cat="Strings")
def _strrep(ip, args, nargout):
    return str_arg(args[0]).replace(str_arg(args[1]), str_arg(args[2]))


@builtin("strtrim", sig="strtrim(s)", en="Remove leading/trailing whitespace", ar="حذف المسافات من بداية النص ونهايته", cat="Strings")
def _strtrim(ip, args, nargout):
    return str_arg(args[0]).strip()


@builtin("contains", sig="contains(s, pattern)", en="True if pattern is in string", ar="التحقق من احتواء النص على نمط معين", cat="Strings")
def _contains(ip, args, nargout):
    return np.array([[str_arg(args[1]) in str_arg(args[0])]])


@builtin("strsplit", sig="strsplit(s, delim)", en="Split string", ar="تقسيم نص", cat="Strings")
def _strsplit(ip, args, nargout):
    s = str_arg(args[0])
    parts = s.split(args[1]) if len(args) > 1 else s.split()
    return Cell(parts)


@builtin("char", sig="char(x)", en="Convert to character array", ar="تحويل إلى أحرف", cat="Strings")
def _char(ip, args, nargout):
    v = args[0]
    if isinstance(v, str):
        return v
    return "".join(chr(int(c)) for c in num_arg(v).real.ravel())


@builtin("double", sig="double(x)", en="Convert to double", ar="تحويل إلى عدد", cat="Strings")
def _double(ip, args, nargout):
    return to_array(args[0]).astype(float) if not np.iscomplexobj(to_array(args[0])) else to_array(args[0])


@builtin("logical", sig="logical(x)", en="Convert to logical", ar="تحويل إلى منطقي", cat="Data")
def _logical(ip, args, nargout):
    return num_arg(args[0]) != 0


@builtin("not", sig="not(x)", en="Logical NOT", ar="نفي منطقي", cat="Data")
def _not(ip, args, nargout):
    return num_arg(args[0]) == 0


@builtin("xor", sig="xor(a, b)", en="Logical exclusive OR", ar="العملية المنطقية (أو الحصرية)", cat="Data")
def _xor(ip, args, nargout):
    return (num_arg(args[0]) != 0) ^ (num_arg(args[1]) != 0)


@builtin("and", sig="and(a, b)", en="Logical AND", ar="العملية المنطقية (و)", cat="Data")
def _and(ip, args, nargout):
    return (num_arg(args[0]) != 0) & (num_arg(args[1]) != 0)


@builtin("or", sig="or(a, b)", en="Logical OR", ar="العملية المنطقية (أو)", cat="Data")
def _or(ip, args, nargout):
    return (num_arg(args[0]) != 0) | (num_arg(args[1]) != 0)


# ---------------------------------------------------------------------------
# structs, cells, types
# ---------------------------------------------------------------------------

@builtin("struct", sig="struct('f1', v1, ...)", en="Create a structure", ar="إنشاء بنية بيانات (struct)", cat="Data")
def _struct(ip, args, nargout):
    s = Struct()
    for k in range(0, len(args) - 1, 2):
        s[str_arg(args[k], "field name")] = args[k + 1]
    return s


@builtin("fieldnames", sig="fieldnames(s)", en="Field names of a structure", ar="أسماء الحقول", cat="Data")
def _fieldnames(ip, args, nargout):
    if not isinstance(args[0], Struct):
        raise MatlabError("Input must be a struct.")
    return Cell(list(args[0].keys()), (len(args[0]), 1))


@builtin("isfield", sig="isfield(s, name)", en="True if field exists", ar="التحقق من وجود الحقل", cat="Data")
def _isfield(ip, args, nargout):
    return np.array([[isinstance(args[0], Struct) and args[1] in args[0]]])


@builtin("cell", sig="cell(n)", en="Create empty cell array", ar="إنشاء مصفوفة خلايا (cell) فارغة", cat="Data")
def _cell(ip, args, nargout):
    r, c = _shape_args(args, "cell")
    return Cell([np.zeros((0, 0)) for _ in range(r * c)], (r, c))


@builtin("class", sig="class(x)", en="Class name of a value", ar="نوع القيمة", cat="Data")
def _class(ip, args, nargout):
    return class_name(args[0])


@builtin("isa", sig="isa(x, 'class')", en="True if value is of a class", ar="التحقق من نوع القيمة", cat="Data")
def _isa(ip, args, nargout):
    cn = class_name(args[0])
    want = str_arg(args[1])
    ok = cn == want or (want == "numeric" and cn == "double") or (want == "float" and cn == "double")
    return np.array([[ok]])


# ---------------------------------------------------------------------------
# workspace & environment
# ---------------------------------------------------------------------------

@builtin("clc", sig="clc", en="Clear the Command Window", ar="مسح نافذة الأوامر", cat="Environment")
def _clc(ip, args, nargout):
    if ip.on_clc:
        ip.on_clc()


@builtin("clear", "clearvars", sig="clear / clear x y", en="Remove variables from the workspace",
         ar="حذف المتغيرات", cat="Environment")
def _clear(ip, args, nargout):
    names = [a for a in args if isinstance(a, str)]
    if not names or names == ["all"] or names == ["variables"]:
        ip.vars.clear()
        if names == ["all"]:
            ip.functions.clear()
        return
    for n in names:
        ip.vars.pop(n, None)


@builtin("who", sig="who", en="List variable names", ar="عرض أسماء المتغيرات", cat="Environment")
def _who(ip, args, nargout):
    names = sorted(ip.vars)
    if names:
        ip.write("\nYour variables are:\n\n" + "  ".join(names) + "\n\n")


@builtin("whos", sig="whos", en="List variables with sizes and classes", ar="عرض المتغيرات بالتفصيل", cat="Environment")
def _whos(ip, args, nargout):
    lines = ["  Name          Size            Class"]
    for n in sorted(ip.vars):
        v = ip.vars[n]
        s = size_of(v)
        lines.append(f"  {n:<13} {f'{s[0]}x{s[1]}':<15} {class_name(v)}")
    ip.write("\n".join(lines) + "\n\n")


@builtin("exist", sig="exist(name)", en="Check if a variable or function exists", ar="التحقق من وجود متغير أو دالة", cat="Environment")
def _exist(ip, args, nargout):
    n = str_arg(args[0])
    if n in ip.vars:
        return arr(1)
    if n in ip.functions or n in ip.builtins:
        return arr(5 if n in ip.builtins else 2)
    return arr(0)


@builtin("format", sig="format long / format short", en="Set output display format",
         ar="تغيير طريقة عرض الأرقام", cat="Environment")
def _format(ip, args, nargout):
    mode = args[0].lower() if args else "short"
    ip.format_long = mode == "long"


_TIC = [time.perf_counter()]


@builtin("tic", sig="tic", en="Start a stopwatch timer", ar="بدء المؤقت", cat="Environment")
def _tic(ip, args, nargout):
    _TIC[0] = time.perf_counter()


@builtin("toc", sig="toc", en="Elapsed time since tic", ar="الوقت المنقضي", cat="Environment")
def _toc(ip, args, nargout):
    dt = time.perf_counter() - _TIC[0]
    if nargout:
        return arr(dt)
    ip.write(f"Elapsed time is {dt:.6f} seconds.\n")


@builtin("pause", sig="pause(t)", en="Pause execution for t seconds", ar="إيقاف مؤقت", cat="Environment")
def _pause(ip, args, nargout):
    if args:
        t = float(scalar(args[0]))
        end = time.perf_counter() + min(max(t, 0), 10)
        while time.perf_counter() < end:
            ip.check_stop()
            time.sleep(0.02)


@builtin("drawnow", sig="drawnow", en="Update figures", ar="تحديث الرسوم", cat="Environment")
def _drawnow(ip, args, nargout):
    pass


@builtin("beep", sig="beep", en="Produce a beep", ar="إصدار صوت تنبيه", cat="Environment")
def _beep(ip, args, nargout):
    pass


@builtin("error", sig="error(msg, ...)", en="Throw an error", ar="إظهار خطأ وإيقاف التنفيذ", cat="Environment")
def _error(ip, args, nargout):
    msg = mformat(args[0], args[1:]) if args and isinstance(args[0], str) else "Error"
    raise MatlabError(msg)


@builtin("warning", sig="warning(msg, ...)", en="Display a warning", ar="عرض تحذير", cat="Environment")
def _warning(ip, args, nargout):
    if args and isinstance(args[0], str) and args[0] in ("on", "off", "query"):
        return
    msg = mformat(args[0], args[1:]) if args else ""
    ip.write(f"Warning: {msg}\n")


@builtin("input", sig="input(prompt)", en="Ask the user for a value", ar="إدخال قيمة من المستخدم", cat="Environment")
def _input(ip, args, nargout):
    if getattr(ip, "on_input", None) is None:
        raise MatlabError("input() is not available here.")
    prompt = args[0] if args else ""
    text = ip.on_input(prompt)
    if text is None:
        raise MatlabError("Input cancelled.")
    if len(args) > 1 and args[1] == "s":
        return text
    from ..parser import parse
    from .. import ast as A
    prog = parse(text)
    if len(prog.body) != 1 or not isinstance(prog.body[0], A.ExprStmt):
        raise MatlabError("Invalid input expression.")
    return ip.eval(prog.body[0].expr)


@builtin("version", "ver", sig="ver", en="Program version", ar="إصدار البرنامج", cat="Environment")
def _ver(ip, args, nargout):
    from ... import __version__
    s = f"HadaraLab Version {__version__}"
    if nargout:
        return s
    ip.write("-" * 60 + f"\n{s}\nOpen-source software (MIT License)\n"
             "MATLAB-like environment for Control Engineering Fundamentals\n"
             "Developed by: Mohammed Abd Alrahman  -  https://mohmadev.com/\n"
             "Support: support@mohmadev.com\n" + "-" * 60 + "\n")


@builtin("help", "doc", sig="help name", en="Show help for a function", ar="عرض المساعدة لدالة", cat="Environment")
def _help(ip, args, nargout):
    from . import HELP
    if not args:
        cats = {}
        for n, (sig, en, ar, cat) in sorted(HELP.items()):
            cats.setdefault(cat, []).append(n)
        out = ["HadaraLab functions (type  help name  for details):\n"]
        for cat in sorted(cats):
            out.append(f"  {cat}:")
            names = cats[cat]
            for k in range(0, len(names), 8):
                out.append("     " + "  ".join(names[k:k + 8]))
        ip.write("\n".join(out) + "\n\n")
        return
    name = args[0]
    if name not in HELP:
        ip.write(f"No help found for '{name}'.\n")
        return
    sig, en, ar, cat = HELP[name]
    ip.write(f"\n  {sig}\n\n  {en}\n  {ar}\n\n")


# ---------------------------------------------------------------------------
# functions of functions
# ---------------------------------------------------------------------------

def _handle(ip, v):
    if isinstance(v, FunctionHandle):
        return v
    if isinstance(v, str):
        return FunctionHandle(name=v)
    raise MatlabError("Expected a function handle, e.g. @(x) x.^2")


@builtin("feval", sig="feval(f, args...)", en="Evaluate a function", ar="تنفيذ دالة", cat="Functions")
def _feval(ip, args, nargout):
    outs = ip.call_handle(_handle(ip, args[0]), list(args[1:]), max(nargout, 1))
    return Multi(outs)


@builtin("func2str", sig="func2str(f)", en="Function handle to string", ar="تحويل مقبض دالة إلى نص", cat="Functions")
def _func2str(ip, args, nargout):
    return repr(_handle(ip, args[0]))


@builtin("str2func", sig="str2func(s)", en="String to function handle", ar="تحويل نص إلى مقبض دالة", cat="Functions")
def _str2func(ip, args, nargout):
    s = str_arg(args[0])
    if s.startswith("@"):
        from ..parser import parse
        prog = parse(s)
        return ip.eval(prog.body[0].expr)
    return FunctionHandle(name=s)


@builtin("arrayfun", sig="arrayfun(f, X)", en="Apply function to each element", ar="تطبيق دالة على كل عنصر", cat="Functions")
def _arrayfun(ip, args, nargout):
    h = _handle(ip, args[0])
    arrays = [num_arg(a) for a in args[1:] if not isinstance(a, str)]
    shape = arrays[0].shape
    out = np.zeros(shape, dtype=complex)
    for idx in np.ndindex(shape):
        vals = [np.array([[a[idx]]]) for a in arrays]
        out[idx] = scalar(ip.call_value(h, *vals))
    return simplify(out)


@builtin("fzero", sig="fzero(f, x0)", en="Find a root of a scalar function", ar="إيجاد جذر دالة", cat="Functions")
def _fzero(ip, args, nargout):
    from scipy.optimize import brentq, fsolve
    h = _handle(ip, args[0])

    def f(x):
        return float(np.real(scalar(ip.call_value(h, np.array([[x]])))))
    x0 = vector(args[1])
    if x0.size >= 2:
        return arr(brentq(f, float(x0[0]), float(x0[1])))
    x0 = float(x0[0])
    fx0 = f(x0)
    if fx0 == 0:
        return arr(x0)
    dx = max(abs(x0) * 0.02, 0.02)
    for _ in range(60):
        for a, b in ((x0 - dx, x0), (x0, x0 + dx)):
            try:
                if np.sign(f(a)) != np.sign(f(b)):
                    return arr(brentq(f, a, b))
            except (ValueError, OverflowError):
                pass
        dx *= 1.6
    return arr(float(fsolve(f, x0)[0]))


@builtin("fminsearch", sig="fminsearch(f, x0)", en="Unconstrained minimization (Nelder-Mead)",
         ar="إيجاد القيمة الصغرى", cat="Functions")
def _fminsearch(ip, args, nargout):
    from scipy.optimize import minimize
    h = _handle(ip, args[0])
    x0 = num_arg(args[1])
    shape = x0.shape

    def f(x):
        return float(np.real(scalar(ip.call_value(h, x.reshape(shape)))))
    res = minimize(f, x0.ravel().astype(float), method="Nelder-Mead",
                   options={"xatol": 1e-4, "fatol": 1e-4, "maxiter": 200 * x0.size})
    return Multi([res.x.reshape(shape), arr(res.fun)])


@builtin("integral", "quad", sig="integral(f, a, b)", en="Numerical integration", ar="التكامل العددي", cat="Functions")
def _integral(ip, args, nargout):
    from scipy.integrate import quad
    h = _handle(ip, args[0])

    def f(x):
        return float(np.real(scalar(ip.call_value(h, np.array([[x]])))))
    val, _ = quad(f, float(scalar(args[1])), float(scalar(args[2])), limit=200)
    return arr(val)


@builtin("ode45", "ode23", sig="[t, x] = ode45(@(t,x) f, [t0 tf], x0)", en="Solve ODEs (Runge-Kutta)",
         ar="حل المعادلات التفاضلية", cat="Functions")
def _ode45(ip, args, nargout):
    from scipy.integrate import solve_ivp
    h = _handle(ip, args[0])
    tspan = vector(args[1]).astype(float)
    y0 = vector(args[2]).astype(float)

    def f(t, y):
        r = ip.call_value(h, np.array([[t]]), y.reshape(-1, 1))
        return vector(r).astype(float)
    t_eval = tspan if tspan.size > 2 else None
    sol = solve_ivp(f, (tspan[0], tspan[-1]), y0, method="RK45", t_eval=t_eval,
                    rtol=1e-3, atol=1e-6, max_step=(tspan[-1] - tspan[0]) / 100)
    if not sol.success:
        raise MatlabError(f"ode45 failed: {sol.message}")
    t = col(sol.t)
    y = sol.y.T
    if nargout == 0:
        fm = ip.figures
        ax = fm.plot_axes()
        for k in range(y.shape[1]):
            ax.plot(sol.t, y[:, k], marker="o", markersize=2.5, linewidth=1.2)
        return None
    return Multi([t, y])
