"""Control-system builtins (Control Engineering Fundamentals syllabus)."""

import numpy as np

from . import builtin
from .core import int_arg, num_arg, str_arg
from ..errors import MatlabError
from ..values import Multi, Struct, col, row, scalar, simplify, to_array, vector
from ...control import analysis as an
from ...control.tf import (TransferFunction, clean_poly, feedback, minreal,
                           parallel, pid, poly_to_str, series, ss2tf, tf2ss,
                           zpk)
from ...graphics import PALETTE, MATLAB_COLORS

CAT = "Control"


def tf_arg(v, name="system"):
    if isinstance(v, TransferFunction):
        return v
    a = to_array(v)
    if a.size == 1 and not isinstance(v, str):
        return TransferFunction([a.ravel()[0]], [1.0])
    raise MatlabError(f"Expected a transfer function for {name} (create one with tf(num, den)).")


def poly_arg(v):
    return clean_poly(vector(v))


# ---------------------------------------------------------------------------
# Old calling forms used by Ogata (4th ed.):  f(num, den, ...)  f(A, B, C, D, iu, ...)
# ---------------------------------------------------------------------------

def legacy(args):
    """Detect an old-style model argument list.

    Returns ("tf", G, rest), ("ss", (A, B, C, D), rest) or None.
    """
    if not args or not isinstance(args[0], np.ndarray):
        return None
    n = 0
    while n < len(args) and isinstance(args[n], np.ndarray) and not isinstance(args[n], str):
        n += 1
    if n >= 4:
        A, B, C, D = (to_array(a).astype(float) for a in args[:4])
        if A.size and A.shape[0] == A.shape[1] and B.shape[0] == A.shape[0] \
                and C.shape[1] == A.shape[1] \
                and (D.size <= 1 or D.shape == (C.shape[0], B.shape[1])):
            return "ss", (A, B, C, D), list(args[4:])
    if n >= 2:
        try:
            return "tf", TransferFunction(poly_arg(args[0]), poly_arg(args[1])), list(args[2:])
        except ValueError as e:
            raise MatlabError(str(e))
    return None


def _pop_input_index(rest, B):
    """Old form f(A, B, C, D, iu, ...): the 5th argument selects the input."""
    if rest and isinstance(rest[0], np.ndarray) and rest[0].size == 1:
        iu = int(np.real(rest[0].ravel()[0]))
        if 1 <= iu <= B.shape[1]:
            return iu - 1, rest[1:]
    return None, rest


def ss_models(A, B, C, D, iu):
    """One SISO transfer function per output for input iu (state space kept)."""
    from scipy import signal
    D2 = np.zeros((C.shape[0], B.shape[1])) if D.size == 0 else (
        np.full((C.shape[0], B.shape[1]), D.ravel()[0]) if D.size == 1 else D)
    num, den = signal.ss2tf(A, B, C, D2, input=iu)
    out = []
    for k in range(num.shape[0]):
        G = TransferFunction(clean_poly(np.round(num[k], 12)), clean_poly(np.round(den, 12)))
        G.ss = (A, B, C, D2)
        G.ss_io = (k, iu)
        out.append(G)
    return out


def expand_legacy(ip, args):
    """Replace an old-style model at the start of args by transfer functions."""
    lg = legacy(args)
    if lg is None:
        return args, None
    ip.arg_names = []
    kind, model, rest = lg
    if kind == "tf":
        return [model] + rest, lg
    A, B, C, D = model
    iu, rest = _pop_input_index(rest, B)
    models = ss_models(A, B, C, D, iu or 0)
    return models + rest, (kind, model, rest, iu)


# ---------------------------------------------------------------------------
# model creation
# ---------------------------------------------------------------------------

@builtin("tf", sig="G = tf(num, den)  |  s = tf('s')",
         en="Create a transfer function from numerator/denominator coefficients",
         ar="إنشاء دالة تحويل من معاملات البسط والمقام", cat=CAT)
def _tf(ip, args, nargout):
    if not args:
        raise MatlabError("Not enough input arguments for 'tf'. Usage: G = tf(num, den)")
    if isinstance(args[0], str):
        if args[0] in ("s", "p"):
            return TransferFunction([1.0, 0.0], [1.0])
        raise MatlabError("Use tf('s') to create the Laplace variable.")
    if isinstance(args[0], TransferFunction):
        return args[0]
    num = poly_arg(args[0])
    den = poly_arg(args[1]) if len(args) > 1 and not isinstance(args[1], str) else np.array([1.0])
    try:
        return TransferFunction(num, den)
    except ValueError as e:
        raise MatlabError(str(e))


@builtin("zpk", sig="G = zpk(z, p, k)", en="Create a transfer function from zeros, poles and gain",
         ar="إنشاء دالة تحويل من الأصفار والأقطاب والكسب", cat=CAT)
def _zpk(ip, args, nargout):
    if len(args) == 1 and isinstance(args[0], str):
        return TransferFunction([1.0, 0.0], [1.0])
    if len(args) != 3:
        raise MatlabError("Usage: G = zpk(z, p, k)")
    z = vector(args[0]) if to_array(args[0]).size else np.array([])
    p = vector(args[1]) if to_array(args[1]).size else np.array([])
    return zpk(z, p, float(np.real(scalar(args[2]))))


@builtin("ss", sig="G = ss(A, B, C, D)", en="State-space model (converted to a transfer function)",
         ar="نموذج فضاء الحالة (يُحوّل إلى دالة تحويل)", cat=CAT)
def _ss(ip, args, nargout):
    if len(args) == 1:
        return tf_arg(args[0])
    if len(args) != 4:
        raise MatlabError("Usage: sys = ss(A, B, C, D)")
    A_, B_, C_, D_ = (num_arg(a).astype(float) for a in args)
    if A_.shape[0] != A_.shape[1] or B_.shape[0] != A_.shape[0] or C_.shape[1] != A_.shape[1]:
        raise MatlabError("The A, B, C, D matrices have inconsistent dimensions.")
    G = ss_models(A_, B_, C_, D_, 0)[0]
    if B_.shape[1] > 1 or C_.shape[0] > 1:
        ip.write("Note: MIMO model - transfer-function functions use input 1 / output 1; "
                 "step and initial show every output.\n")
    return G


@builtin("ss2tf", sig="[num, den] = ss2tf(A, B, C, D, iu)", en="State space to transfer function",
         ar="تحويل من فضاء الحالة إلى دالة تحويل", cat=CAT)
def _ss2tf(ip, args, nargout):
    from scipy import signal
    A_, B_, C_, D_ = (num_arg(a).astype(float) for a in args[:4])
    iu = int_arg(args[4]) - 1 if len(args) > 4 else 0
    if D_.size <= 1:
        D_ = np.full((C_.shape[0], B_.shape[1]), D_.ravel()[0] if D_.size else 0.0)
    num, den = signal.ss2tf(A_, B_, C_, D_, input=iu)
    num = np.where(np.abs(num) < 1e-12, 0.0, np.round(num, 12))
    return Multi([np.atleast_2d(num), row(np.round(den, 12))])


@builtin("tf2ss", sig="[A, B, C, D] = tf2ss(num, den)", en="Transfer function to state space (controllable form)",
         ar="تحويل دالة التحويل إلى فضاء الحالة", cat=CAT)
def _tf2ss(ip, args, nargout):
    G = args[0] if isinstance(args[0], TransferFunction) else TransferFunction(poly_arg(args[0]), poly_arg(args[1]))
    A_, B_, C_, D_ = tf2ss(G)
    return Multi([np.atleast_2d(A_), np.atleast_2d(B_), np.atleast_2d(C_), np.atleast_2d(D_)])


@builtin("tf2zp", sig="[z, p, k] = tf2zp(num, den)", en="Transfer function to zero-pole-gain",
         ar="تحويل إلى أصفار وأقطاب وكسب", cat=CAT)
def _tf2zp(ip, args, nargout):
    G = TransferFunction(poly_arg(args[0]), poly_arg(args[1]))
    k = G.num[0] / G.den[0]
    return Multi([simplify(col(G.zeros())) if G.zeros().size else np.zeros((0, 1)),
                  simplify(col(G.poles())), np.array([[k]])])


@builtin("zp2tf", sig="[num, den] = zp2tf(z, p, k)", en="Zero-pole-gain to transfer function",
         ar="تحويل الأصفار والأقطاب إلى دالة تحويل", cat=CAT)
def _zp2tf(ip, args, nargout):
    G = _zpk(ip, args, 1)
    return Multi([row(G.num), row(G.den)])


@builtin("tfdata", sig="[num, den] = tfdata(G, 'v')", en="Numerator and denominator of a transfer function",
         ar="استخراج البسط والمقام", cat=CAT)
def _tfdata(ip, args, nargout):
    G = tf_arg(args[0])
    return Multi([row(G.num), row(G.den)])


@builtin("zpkdata", sig="[z, p, k] = zpkdata(G, 'v')", en="Zeros, poles and gain of a system",
         ar="استخراج الأصفار والأقطاب والكسب", cat=CAT)
def _zpkdata(ip, args, nargout):
    G = tf_arg(args[0])
    z = G.zeros()
    return Multi([simplify(col(z)) if z.size else np.zeros((0, 1)), simplify(col(G.poles())),
                  np.array([[G.num[0] / G.den[0]]])])


@builtin("pid", sig="C = pid(Kp, Ki, Kd)", en="PID controller  C(s) = Kp + Ki/s + Kd*s",
         ar="متحكم PID", cat=CAT)
def _pid(ip, args, nargout):
    vals = [float(np.real(scalar(a))) for a in args[:4]]
    while len(vals) < 3:
        vals.append(0.0)
    return pid(*vals)


@builtin("ord2", sig="[num, den] = ord2(wn, zeta)", en="Second-order system 1/(s^2+2*zeta*wn*s+wn^2) (multiply num by wn^2 for unity DC gain)",
         ar="نظام من الدرجة الثانية: 1/(s^2+2ζωn s+ωn^2)", cat=CAT)
def _ord2(ip, args, nargout):
    wn, z = float(scalar(args[0])), float(scalar(args[1]))
    G = TransferFunction([1.0], [1, 2 * z * wn, wn ** 2])
    if nargout >= 2:
        return Multi([row(G.num), row(G.den)])
    return G


@builtin("printsys", sig="printsys(num, den)", en="Print a transfer function", ar="طباعة دالة التحويل", cat=CAT)
def _printsys(ip, args, nargout):
    G = TransferFunction(poly_arg(args[0]), poly_arg(args[1]))
    ip.write(f"\nnum/den = \n\n{G.to_str()}\n\n")


# ---------------------------------------------------------------------------
# interconnection
# ---------------------------------------------------------------------------

@builtin("series", sig="G = series(G1, G2)", en="Series (cascade) connection G1*G2",
         ar="توصيل على التوالي", cat=CAT)
def _series(ip, args, nargout):
    return series(*(tf_arg(a) for a in args))


@builtin("parallel", sig="G = parallel(G1, G2)", en="Parallel connection G1+G2",
         ar="توصيل على التوازي", cat=CAT)
def _parallel(ip, args, nargout):
    return parallel(*(tf_arg(a) for a in args))


@builtin("feedback", sig="T = feedback(G, H)  |  feedback(G, H, +1)",
         en="Closed-loop system G/(1+G*H) (negative feedback by default)",
         ar="نظام الحلقة المغلقة (تغذية عكسية)", cat=CAT)
def _feedback(ip, args, nargout):
    if not args:
        raise MatlabError("Usage: T = feedback(G, H)")
    G = tf_arg(args[0])
    H = tf_arg(args[1]) if len(args) > 1 else TransferFunction([1.0], [1.0])
    sign = float(scalar(args[2])) if len(args) > 2 else -1.0
    return feedback(G, H, 1 if sign > 0 else -1)


@builtin("minreal", sig="G = minreal(G)", en="Cancel common poles and zeros",
         ar="حذف الأقطاب والأصفار المشتركة", cat=CAT)
def _minreal(ip, args, nargout):
    tol = float(scalar(args[1])) if len(args) > 1 else 1e-5
    return minreal(tf_arg(args[0]), tol)


# ---------------------------------------------------------------------------
# properties
# ---------------------------------------------------------------------------

@builtin("pole", sig="p = pole(G)", en="Poles of a system (roots of the denominator)",
         ar="أقطاب النظام", cat=CAT)
def _pole(ip, args, nargout):
    return simplify(col(tf_arg(args[0]).poles()))


@builtin("zero", sig="z = zero(G)", en="Zeros of a system (roots of the numerator)",
         ar="أصفار النظام", cat=CAT)
def _zero(ip, args, nargout):
    z = tf_arg(args[0]).zeros()
    return simplify(col(z)) if z.size else np.zeros((0, 1))


@builtin("dcgain", sig="k = dcgain(G)", en="Steady-state (DC) gain G(0)",
         ar="الكسب عند الحالة المستقرة", cat=CAT)
def _dcgain(ip, args, nargout):
    return np.array([[tf_arg(args[0]).dcgain()]])


@builtin("evalfr", sig="evalfr(G, s)", en="Evaluate G at a complex value s",
         ar="حساب قيمة دالة التحويل عند s", cat=CAT)
def _evalfr(ip, args, nargout):
    return simplify(np.array([[tf_arg(args[0])(complex(scalar(args[1])))]]))


@builtin("order", sig="n = order(G)", en="System order", ar="رتبة النظام", cat=CAT)
def _order(ip, args, nargout):
    return np.array([[float(tf_arg(args[0]).order)]])


@builtin("isstable", sig="isstable(G)", en="True if all poles are in the left-half plane",
         ar="التحقق من استقرارية النظام", cat=CAT)
def _isstable(ip, args, nargout):
    p = tf_arg(args[0]).poles()
    return np.array([[bool(np.all(p.real < 0))]])


@builtin("damp", sig="damp(G)  |  [wn, zeta, p] = damp(G)", en="Natural frequency and damping of the poles",
         ar="التردد الطبيعي ونسبة الإخماد للأقطاب", cat=CAT)
def _damp(ip, args, nargout):
    v = args[0]
    if isinstance(v, np.ndarray) and v.size > 1:
        a = to_array(v)
        # damp(den) for a polynomial, damp(A) for a square matrix
        G = TransferFunction([1.0], np.poly(a) if a.shape[0] == a.shape[1] else poly_arg(a))
    else:
        G = tf_arg(v)
    p, wn, zeta, tau = an.damp(G)
    if nargout:
        return Multi([col(wn), col(zeta), simplify(col(p))])
    lines = ["", "         Pole              Damping       Frequency      Time Constant",
             "                                        (rad/seconds)      (seconds)", ""]
    for pi_, w, z, t in zip(p, wn, zeta, tau):
        if abs(pi_.imag) > 1e-12:
            ps = f"{pi_.real:.2e} {'+' if pi_.imag >= 0 else '-'} {abs(pi_.imag):.2e}i"
        else:
            ps = f"{pi_.real:.2e}"
        ts = "Inf" if np.isinf(t) else f"{t:.2e}"
        lines.append(f"  {ps:<24}{z:>10.2e}{w:>14.2e}{ts:>16}")
    ip.write("\n".join(lines) + "\n\n")


# ---------------------------------------------------------------------------
# plotting helpers
# ---------------------------------------------------------------------------

def _split_systems(ip, args):
    """Parse (sys1, 'r--', sys2, ..., extra) style argument lists."""
    args, _ = expand_legacy(ip, args)
    systems = []
    extra = []
    names = list(getattr(ip, "arg_names", []) or [])
    for k, a in enumerate(args):
        if isinstance(a, TransferFunction):
            systems.append([a, None, names[k] if k < len(names) else None])
        elif isinstance(a, str) and systems:
            systems[-1][1] = a
        else:
            extra.append(a)
    if not systems:
        raise MatlabError("Expected at least one transfer function argument.")
    return systems, extra


def _style_kwargs(spec, k):
    color = PALETTE[k % len(PALETTE)]
    kw = {"color": color, "linewidth": 1.8}
    if spec:
        ls = "-"
        for token in ("--", "-.", ":", "-"):
            if token in spec:
                ls = token
                break
        kw["linestyle"] = ls
        for ch in spec:
            if ch in MATLAB_COLORS:
                kw["color"] = MATLAB_COLORS[ch]
        for m in "o+*.xsd^v<>ph":
            if m in spec:
                kw["marker"] = m
                kw["markersize"] = 4
                if "-" not in spec and ":" not in spec:
                    kw["linestyle"] = "none"
    return kw


def _finish(ip, ax, title, xlabel, ylabel, systems):
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ip.figures.apply_grid(ax, True)
    labels = [s[2] for s in systems]
    if len(systems) > 1 or ax._hl_hold:
        handles, existing = ax.get_legend_handles_labels()
        if any(l and not l.startswith("_") for l in existing):
            ax.legend(fontsize=8, framealpha=0.9)


def _time_arg(extra):
    for e in extra:
        if isinstance(e, (str,)) or not isinstance(e, np.ndarray):
            continue
        a = to_array(e)
        if a.size == 1:
            tf_ = float(np.real(a.ravel()[0]))
            if not np.isfinite(tf_) or tf_ <= 0:
                raise MatlabError("The final time must be a positive number, e.g. step(G, 10).")
            return tf_, None
        if a.size > 1:
            t = np.real(a.ravel()).astype(float)
            if np.any(np.diff(t) <= 0) or not np.all(np.isfinite(t)):
                raise MatlabError("The time vector must be increasing, e.g. t = 0:0.01:10.")
            return None, t
        if isinstance(e, np.ndarray) and a.size == 0 and e.shape != (0, 0):
            raise MatlabError("The time vector is empty. Check its definition, e.g. t = 0:0.01:10.")
    return None, None


def _common_time(systems, tfinal, tvec):
    if tvec is not None:
        return tvec
    if tfinal is None:
        tfinal = max(an.auto_time(s[0])[-1] for s in systems)
    npts = max(len(an.auto_time(s[0], tfinal=tfinal)) for s in systems)
    return np.linspace(0, tfinal, npts)


def _ss_of(G):
    """State-space data for G: the ss() model if it has one, else tf2ss."""
    if getattr(G, "ss", None) is not None:
        A, B, C, D = G.ss
        out, iu = getattr(G, "ss_io", (0, 0))
        return A, B, C, D, iu, out
    A, B, C, D = tf2ss(G)
    return A, B, C, D, 0, 0


def _time_response(ip, args, nargout, kind):
    old_style = legacy(args) is not None
    systems, extra = _split_systems(ip, args)
    tfinal, tvec = _time_arg(extra)
    fn = an.step_response if kind == "step" else an.impulse_response
    try:
        if nargout:
            G = systems[0][0]
            t = tvec if tvec is not None else (an.auto_time(G, tfinal) if tfinal else an.auto_time(G))
            if nargout >= 3 or getattr(G, "ss", None) is not None:
                A, B, C, D, iu, out = _ss_of(G)
                y, x = an.ss_time_response(A, B, C, D, kind, t, iu)
                if getattr(G, "ss", None) is None:
                    y = y[:, :1]
            else:
                t, y = fn(G, t)
                y, x = col(y), np.zeros((len(t), 0))
            # Ogata 4th ed.: [y, x, t] = step(num, den, t) ; newer: [y, t, x] = step(sys)
            if old_style:
                return Multi([y, x, col(t)])
            return Multi([y, col(t), x])
        t = _common_time(systems, tfinal, tvec)
        ax = ip.figures.plot_axes()
        offset = len(ax.get_lines())
        plotted_ss = set()
        for k, (G, spec, name) in enumerate(systems):
            if getattr(G, "ss", None) is not None:
                # state-space model: plot every output once
                key = id(G.ss[0])
                if key in plotted_ss:
                    continue
                plotted_ss.add(key)
                A, B, C, D, iu, _ = _ss_of(G)
                y, _x = an.ss_time_response(A, B, C, D, kind, t, iu)
                for j in range(y.shape[1]):
                    kw = _style_kwargs(spec, k + j + offset)
                    lab = (name or "sys") + (f" : y{j + 1}" if y.shape[1] > 1 else "")
                    ax.plot(t, y[:, j], label=lab if (y.shape[1] > 1 or len(systems) > 1) else "_nolegend_", **kw)
                continue
            tt, y = fn(G, t)
            kw = _style_kwargs(spec, k + offset)
            label = name or (f"sys{k + 1}" if len(systems) > 1 else None)
            line, = ax.plot(tt, y, label=label or "_nolegend_", **kw)
            line._hl_kind = kind
            if kind == "step":
                dc = G.dcgain()
                if np.isfinite(dc) and np.all(G.poles().real < 0):
                    ax.axhline(dc, color=kw["color"], linestyle=":", linewidth=0.9, alpha=0.7)
        ax.set_xlim(t[0], t[-1])
        title = "Step Response" if kind == "step" else "Impulse Response"
        _finish(ip, ax, title, "Time (seconds)", "Amplitude", systems)
        ax._hl_kind = kind
    except ValueError as e:
        raise MatlabError(str(e))
    return None


@builtin("step", sig="step(G)  |  step(G1, G2, Tfinal)  |  [y, t] = step(G)",
         en="Step response of a system", ar="الاستجابة لدالة الخطوة (Step)", cat=CAT)
def _step(ip, args, nargout):
    return _time_response(ip, args, nargout, "step")


@builtin("impulse", sig="impulse(G)  |  [y, t] = impulse(G)", en="Impulse response of a system",
         ar="الاستجابة للنبضة (Impulse)", cat=CAT)
def _impulse(ip, args, nargout):
    return _time_response(ip, args, nargout, "impulse")


@builtin("lsim", sig="lsim(G, u, t)  |  y = lsim(G, u, t)", en="Response to an arbitrary input signal",
         ar="الاستجابة لإشارة دخل اختيارية", cat=CAT)
def _lsim(ip, args, nargout):
    args, lg = expand_legacy(ip, args)
    if lg is not None and lg[0] == "ss":
        args = [args[0]] + list(lg[2])      # first output model, then u, t
    if len(args) < 3:
        raise MatlabError("Usage: lsim(G, u, t)")
    G = tf_arg(args[0])
    u = np.real(vector(args[1])).astype(float)
    t = np.real(vector(args[2])).astype(float)
    try:
        if getattr(G, "ss", None) is not None or (lg is not None and nargout >= 2):
            A, B, C, D, iu, _ = _ss_of(G)
            if u.size == 1:
                u = np.full_like(t, u[0])
            y_all, x = an.ss_time_response(A, B, C, D, "lsim", t, iu, u=u)
            y = y_all[:, 0] if getattr(G, "ss", None) is None else y_all
        else:
            t, y = an.lsim_response(G, u, t)
            x = np.zeros((len(t), 0))
    except ValueError as e:
        raise MatlabError(str(e))
    if nargout:
        yv = y if np.ndim(y) == 2 else col(y)
        if lg is not None:
            return Multi([yv, x])                 # old form: [y, x] = lsim(num, den, u, t)
        return Multi([yv, col(t), x])
    y = y[:, 0] if np.ndim(y) == 2 else y
    ax = ip.figures.plot_axes()
    ax.plot(t, u if u.size == t.size else np.full_like(t, u[0]), color="#9AA8BA",
            linewidth=1.2, label="Input u(t)")
    ax.plot(t, y, color=PALETTE[0], linewidth=1.8, label="Output y(t)")
    ax.set_xlim(t[0], t[-1])
    _finish(ip, ax, "Linear Simulation Results", "Time (seconds)", "Amplitude", [[G, None, None]])
    ax.legend(fontsize=8)


@builtin("ramp", sig="ramp(G)  |  ramp(G, Tfinal)", en="Ramp response (input r(t) = t)",
         ar="الاستجابة لدالة الانحدار (Ramp)", cat=CAT)
def _ramp(ip, args, nargout):
    systems, extra = _split_systems(ip, args)
    tfinal, tvec = _time_arg(extra)
    t = _common_time(systems, tfinal, tvec)
    if nargout:
        tt, y = an.lsim_response(systems[0][0], t, t)
        return Multi([col(y), col(tt)])
    ax = ip.figures.plot_axes()
    ax.plot(t, t, color="#9AA8BA", linestyle="--", linewidth=1.2, label="Input r(t) = t")
    for k, (G, spec, name) in enumerate(systems):
        tt, y = an.lsim_response(G, t, t)
        ax.plot(tt, y, label=name or f"sys{k + 1}", **_style_kwargs(spec, k))
    ax.set_xlim(t[0], t[-1])
    _finish(ip, ax, "Ramp Response", "Time (seconds)", "Amplitude", systems)
    ax.legend(fontsize=8)


@builtin("stepinfo", sig="S = stepinfo(G)  |  stepinfo(y, t)",
         en="Rise time, settling time, overshoot and peak of the step response",
         ar="مواصفات الاستجابة: زمن الصعود وزمن الاستقرار والتجاوز الأقصى", cat=CAT)
def _stepinfo(ip, args, nargout):
    if isinstance(args[0], TransferFunction):
        info = an.system_step_info(args[0])
    else:
        y = np.real(vector(args[0])).astype(float)
        t = np.real(vector(args[1])).astype(float) if len(args) > 1 else np.arange(len(y), dtype=float)
        yfinal = float(scalar(args[2])) if len(args) > 2 and not isinstance(args[2], str) else None
        info = an.step_info(t, y, yfinal)
    s = Struct()
    for k in ("RiseTime", "TransientTime", "SettlingTime", "SettlingMin", "SettlingMax",
              "Overshoot", "Undershoot", "Peak", "PeakTime"):
        s[k] = np.array([[info[k]]])
    return s


@builtin("stepspecs", sig="stepspecs(zeta, wn)",
         en="Textbook 2nd-order formulas: Tp, Ts (2%), Tr, %OS (Ogata ch.5)",
         ar="علاقات النظام من الدرجة الثانية: زمن الذروة وزمن الاستقرار والتجاوز", cat=CAT)
def _stepspecs(ip, args, nargout):
    z, wn = float(scalar(args[0])), float(scalar(args[1]))
    if not 0 < z < 1:
        raise MatlabError("stepspecs needs an underdamped system: 0 < zeta < 1.")
    wd = wn * np.sqrt(1 - z ** 2)
    beta = np.arccos(z)
    s = Struct()
    s["wd"] = np.array([[wd]])
    s["RiseTime"] = np.array([[(np.pi - beta) / wd]])
    s["PeakTime"] = np.array([[np.pi / wd]])
    s["Overshoot"] = np.array([[100 * np.exp(-z * np.pi / np.sqrt(1 - z ** 2))]])
    s["SettlingTime2"] = np.array([[4 / (z * wn)]])
    s["SettlingTime5"] = np.array([[3 / (z * wn)]])
    return s


@builtin("ess", sig="ess(G)", en="Error constants Kp, Kv, Ka and steady-state errors (unity feedback, open-loop G)",
         ar="ثوابت الخطأ والخطأ في الحالة المستقرة", cat=CAT)
def _ess(ip, args, nargout):
    G = tf_arg(args[0])
    r = an.steady_state_errors(G)
    if nargout:
        s = Struct()
        for k, v in r.items():
            s[k] = np.array([[v]])
        return s

    def f(x):
        return "Inf" if np.isinf(x) else f"{x:.4g}"
    ip.write("\n  Unity-feedback steady-state analysis (open loop G)\n"
             f"  System type      : {int(r['Type'])}\n"
             f"  Kp (position)    : {f(r['Kp'])}     ess(step)     = {f(r['ess_step'])}\n"
             f"  Kv (velocity)    : {f(r['Kv'])}     ess(ramp)     = {f(r['ess_ramp'])}\n"
             f"  Ka (acceleration): {f(r['Ka'])}     ess(parabola) = {f(r['ess_parabola'])}\n\n")


@builtin("routh", sig="routh(den)  |  routh(G)  |  R = routh(p)",
         en="Routh-Hurwitz stability table of a characteristic polynomial",
         ar="جدول راوث لفحص الاستقرارية", cat=CAT)
def _routh(ip, args, nargout):
    v = args[0]
    p = v.den if isinstance(v, TransferFunction) else poly_arg(v)
    try:
        T, notes, changes = an.routh_array(p)
    except ValueError as e:
        raise MatlabError(str(e))
    if nargout:
        return T
    n = T.shape[0] - 1
    w = max(10, max(len(f"{x:.4g}") for x in T.ravel()) + 2)
    lines = [f"\n  Routh-Hurwitz table for:  {poly_to_str(p)}\n"]
    for i in range(T.shape[0]):
        label = f"s^{n - i}"
        cells = "".join(f"{x:>{w}.4g}" for x in T[i])
        lines.append(f"  {label:>5} |{cells}")
    lines.append("")
    for kind, i, aux in notes:
        if kind == "zero_first":
            lines.append(f"  Note: first element of row s^{n - i} was 0 -> replaced by epsilon.")
        else:
            lines.append(f"  Note: row s^{n - i} was all zeros -> auxiliary polynomial "
                         f"A(s) = {poly_to_str(aux)}, row replaced by dA/ds.")
            r = an.roots(aux)
            lines.append("        Roots of A(s): " + ", ".join(_cfmt(x) for x in r))
    lines.append(f"  Sign changes in first column: {changes}")
    has_zero_row = any(k == "zero_row" for k, _, _ in notes)
    if changes > 0:
        lines.append(f"  => UNSTABLE: {changes} pole(s) in the right-half s-plane.")
    elif has_zero_row:
        lines.append("  => MARGINALLY STABLE: poles on the imaginary axis (see auxiliary polynomial).")
    else:
        lines.append("  => STABLE: all poles are in the left-half s-plane.")
    ip.write("\n".join(lines) + "\n\n")


def _cfmt(x):
    x = complex(x)
    if abs(x.imag) < 1e-9:
        return f"{x.real:.4g}"
    return f"{x.real:.4g}{x.imag:+.4g}j"


@builtin("krange", sig="krange(G)", en="Range of gain K for which the unity-feedback loop K*G is stable",
         ar="مدى الكسب K الذي يجعل النظام مستقراً", cat=CAT)
def _krange(ip, args, nargout):
    G = tf_arg(args[0])
    num, den = G.num, G.den
    cands = sorted({k for k, _ in an.imag_axis_crossings(G)} |
                   ({-np.polyval(den, 0) / np.polyval(num, 0)}
                    if abs(np.polyval(num, 0)) > 1e-12 and -np.polyval(den, 0) / np.polyval(num, 0) > 0 else set()))
    edges = [0.0] + cands + [np.inf]
    stable = []
    for a, b in zip(edges[:-1], edges[1:]):
        k = (a + b) / 2 if np.isfinite(b) else (a * 2 + 1)
        r = np.roots(an._char_poly(num, den, k))
        if np.all(r.real < -1e-9):
            stable.append((a, b))
    if nargout:
        return np.array(stable) if stable else np.zeros((0, 2))
    if not stable:
        ip.write("  The closed loop is unstable for every K > 0.\n\n")
        return
    for a, b in stable:
        ip.write(f"  Closed loop is stable for  {a:.6g} < K < {'Inf' if np.isinf(b) else f'{b:.6g}'}\n")
    for k, wc in an.imag_axis_crossings(G):
        ip.write(f"  Crossing of the jw-axis at K = {k:.6g},  w = {wc:.6g} rad/s\n")
    ip.write("\n")


# ---------------------------------------------------------------------------
# frequency domain
# ---------------------------------------------------------------------------

def _freq_arg(extra):
    for e in extra:
        from ..values import Cell
        if isinstance(e, Cell) and len(e.items) == 2:
            lo, hi = float(np.real(scalar(e.items[0]))), float(np.real(scalar(e.items[1])))
            if lo <= 0 or hi <= lo:
                raise MatlabError("The frequency range {wmin, wmax} needs 0 < wmin < wmax, "
                                  "e.g. bode(G, {0.1, 100}).")
            return np.logspace(np.log10(lo), np.log10(hi), 1000)
        if isinstance(e, str):
            continue
        a = to_array(e)
        if a.size > 1:
            w = np.real(a.ravel()).astype(float)
            if np.any(w <= 0):
                raise MatlabError("Frequencies must be positive, e.g. w = logspace(-1, 2, 500).")
            return w
    return None


def _bode_axes(ip):
    fm = ip.figures
    fig = fm.gcf()
    axes = getattr(fig, "_hl_bode", None)
    hold = getattr(fig, "_hl_hold", False)
    if axes is None or axes[0] not in fig.axes or not hold:
        fm.clear_figure(fig)
        from ...graphics import style_axes
        axm = fig.add_subplot(2, 1, 1)
        axp = fig.add_subplot(2, 1, 2, sharex=axm)
        for ax in (axm, axp):
            style_axes(ax)
            ax._hl_hold = hold
        fig._hl_bode = (axm, axp)
        fig._hl_current_ax = axm
    fm.touch()
    return fig._hl_bode


def _phase_ticks(ax, phase_all):
    lo, hi = np.nanmin(phase_all), np.nanmax(phase_all)
    span = hi - lo
    step = 45 if span <= 270 else 90 if span <= 720 else 180
    t0 = np.floor(lo / step) * step
    t1 = np.ceil(hi / step) * step
    if t1 - t0 < step:
        t0 -= step
        t1 += step
    ax.set_yticks(np.arange(t0, t1 + 1, step))


@builtin("bode", sig="bode(G)  |  bode(G1, G2, {wmin, wmax})  |  [mag, phase, w] = bode(G)",
         en="Bode diagram (magnitude in dB and phase in degrees)",
         ar="مخطط بود (المقدار بالديسيبل والطور بالدرجات)", cat=CAT)
def _bode(ip, args, nargout):
    systems, extra = _split_systems(ip, args)
    w = _freq_arg(extra)
    if nargout:
        G = systems[0][0]
        mag, phase, ww = an.freq_response(G, w if w is not None else an.auto_freq(G))
        return Multi([col(mag), col(phase), col(ww)])
    _plot_bode(ip, systems, w)


def _plot_bode(ip, systems, w=None, title="Bode Diagram"):
    axm, axp = _bode_axes(ip)
    if w is None:
        ws = [an.auto_freq(s[0]) for s in systems]
        w = np.logspace(np.log10(min(x[0] for x in ws)), np.log10(max(x[-1] for x in ws)), 1500)
    offset = len(axm.get_lines())
    phases = [l.get_ydata() for l in axp.get_lines()]
    for k, (G, spec, name) in enumerate(systems):
        mag, phase, _ = an.freq_response(G, w)
        kw = _style_kwargs(spec, k + offset)
        label = name or (f"sys{k + 1}" if len(systems) > 1 else "_nolegend_")
        with np.errstate(divide="ignore"):
            axm.semilogx(w, 20 * np.log10(mag), label=label, **kw)
        axp.semilogx(w, phase, **kw)
        phases.append(phase)
    axm.set_xlim(w[0], w[-1])
    _phase_ticks(axp, np.concatenate(phases))
    axm.set_title(title, fontsize=11, fontweight="bold")
    axm.set_ylabel("Magnitude (dB)")
    axp.set_ylabel("Phase (deg)")
    axp.set_xlabel("Frequency (rad/s)")
    for ax in (axm, axp):
        ip.figures.apply_grid(ax, True)
    axm.tick_params(labelbottom=False)
    if len(systems) > 1 or len(axm.get_lines()) > 1:
        if any(not l.get_label().startswith("_") for l in axm.get_lines()):
            axm.legend(fontsize=8)
    return axm, axp


@builtin("margin", sig="margin(G)  |  [Gm, Pm, Wcg, Wcp] = margin(G)",
         en="Gain margin and phase margin (with annotated Bode plot)",
         ar="هامش الكسب وهامش الطور", cat=CAT)
def _margin(ip, args, nargout):
    args, _ = expand_legacy(ip, args)
    G = tf_arg(args[0])
    Gm, Pm, Wcg, Wcp = an.margins(G)
    if nargout:
        return Multi([np.array([[Gm]]), np.array([[Pm]]), np.array([[Wcg]]), np.array([[Wcp]])])
    gm_db = 20 * np.log10(Gm) if np.isfinite(Gm) else np.inf

    def fm(x, unit=""):
        return "Inf" if not np.isfinite(x) else f"{x:.3g}{unit}"
    title = (f"Bode Diagram\nGm = {fm(gm_db, ' dB')} (at {fm(Wcg)} rad/s),  "
             f"Pm = {fm(Pm, ' deg')} (at {fm(Wcp)} rad/s)")
    ws = [Wcg, Wcp]
    w = an.auto_freq(G)
    lo, hi = w[0], w[-1]
    for x in ws:
        if np.isfinite(x):
            lo, hi = min(lo, x / 10), max(hi, x * 10)
    w = np.logspace(np.log10(lo), np.log10(hi), 1500)
    axm, axp = _plot_bode(ip, [[G, None, None]], w, title)
    axm.title.set_fontsize(10)
    axm.axhline(0, color="#7A8BA3", linestyle="--", linewidth=0.9)
    axp.axhline(-180, color="#7A8BA3", linestyle="--", linewidth=0.9)
    if np.isfinite(Wcg):
        axm.vlines(Wcg, -gm_db, 0, color="#E91E63", linewidth=2)
        axp.axvline(Wcg, color="#E91E63", linestyle=":", linewidth=1)
    if np.isfinite(Wcp):
        mag, phase, _ = an.freq_response(G, np.array([Wcp]))
        axp.vlines(Wcp, -180, phase[0], color="#00BFA5", linewidth=2)
        axm.axvline(Wcp, color="#00BFA5", linestyle=":", linewidth=1)
    ip.write(f"  Gain margin  Gm = {fm(gm_db, ' dB')} ({fm(Gm)} abs) at w = {fm(Wcg)} rad/s\n"
             f"  Phase margin Pm = {fm(Pm, ' deg')} at w = {fm(Wcp)} rad/s\n"
             f"  => Closed loop is {'STABLE' if (Pm > 0 and (not np.isfinite(Gm) or Gm > 1)) else 'UNSTABLE'}"
             " (for minimum-phase systems)\n")


@builtin("bandwidth", sig="bandwidth(G)", en="Frequency where the gain drops 3 dB below DC",
         ar="عرض النطاق الترددي", cat=CAT)
def _bandwidth(ip, args, nargout):
    from scipy.optimize import brentq
    G = tf_arg(args[0])
    dc = abs(G.dcgain())
    if not np.isfinite(dc) or dc == 0:
        return np.array([[np.nan]])
    target = dc / np.sqrt(2)
    w = an.auto_freq(G, 4000)
    w = np.logspace(np.log10(w[0]) - 2, np.log10(w[-1]) + 2, 8000)
    m = np.abs(G(1j * w)) - target
    idx = np.nonzero(np.sign(m[:-1]) != np.sign(m[1:]))[0]
    if idx.size == 0:
        return np.array([[np.inf]])
    i = idx[0]
    return np.array([[brentq(lambda x: abs(G(1j * x)) - target, w[i], w[i + 1])]])


@builtin("nyquist", sig="nyquist(G)", en="Nyquist diagram", ar="مخطط نايكوست", cat=CAT)
def _nyquist(ip, args, nargout):
    systems, extra = _split_systems(ip, args)
    w = _freq_arg(extra)
    if nargout:
        H, ww = an.nyquist_data(systems[0][0], w)
        return Multi([col(H.real), col(H.imag), col(ww)])
    ax = ip.figures.plot_axes()
    pts = []
    for k, (G, spec, name) in enumerate(systems):
        H, ww = an.nyquist_data(G, w)
        ok = np.isfinite(H) & (np.abs(H) < 1e6)
        H = H[ok]
        kw = _style_kwargs(spec, k)
        ax.plot(H.real, H.imag, label=name or "_nolegend_", **kw)
        ax.plot(H.real, -H.imag, linestyle="--", color=kw["color"], linewidth=1.2)
        # direction arrows
        for frac in (0.25, 0.6):
            i = int(frac * (len(H) - 2))
            if 0 <= i < len(H) - 1:
                ax.annotate("", xy=(H.real[i + 1], H.imag[i + 1]), xytext=(H.real[i], H.imag[i]),
                            arrowprops=dict(arrowstyle="-|>", color=kw["color"], lw=1.5))
        pts.append(H)
    ax.plot([-1], [0], marker="+", color="#E53935", markersize=12, markeredgewidth=2)
    allp = np.concatenate(pts)
    rx = np.percentile(np.abs(allp.real), 97) if allp.size else 1
    ry = np.percentile(np.abs(allp.imag), 97) if allp.size else 1
    r = max(rx, ry, 1.2) * 1.15
    ax.set_xlim(min(-1.3, np.min(allp.real[np.abs(allp.real) <= r])) * 1.1 if allp.size else -2,
                max(0.3, np.max(allp.real[np.abs(allp.real) <= r]) * 1.1) if allp.size else 2)
    ax.set_ylim(-r, r)
    ax.axhline(0, color="#B8C7D9", linewidth=0.8)
    ax.axvline(0, color="#B8C7D9", linewidth=0.8)
    _finish(ip, ax, "Nyquist Diagram", "Real Axis", "Imaginary Axis", systems)


# ---------------------------------------------------------------------------
# root locus & pole-zero map
# ---------------------------------------------------------------------------

def _mark_poles_zeros(ax, G, color="#1E88E5"):
    p, z = G.poles(), G.zeros()
    ax.plot(p.real, p.imag, linestyle="none", marker="x", markersize=10, markeredgewidth=2.2,
            color=color, label="_nolegend_")
    if z.size:
        ax.plot(z.real, z.imag, linestyle="none", marker="o", markersize=9, markeredgewidth=2,
                markerfacecolor="white", color=color, label="_nolegend_")


@builtin("rlocus", sig="rlocus(G)  |  rlocus(G, K)  |  [r, K] = rlocus(G)",
         en="Root locus of the closed-loop poles of 1 + K*G(s) = 0",
         ar="المحل الهندسي للجذور (Root Locus)", cat=CAT)
def _rlocus(ip, args, nargout):
    args, lg = expand_legacy(ip, args)
    G = tf_arg(args[0])
    gains = vector(args[1]).astype(float) if len(args) > 1 and not isinstance(args[1], str) else None
    try:
        k, r = an.rlocus_data(G, gains)
    except ValueError as e:
        raise MatlabError(str(e))
    if nargout:
        # old form [r, K] = rlocus(num, den): one ROW per gain (plot(r, 'o') works)
        return Multi([simplify(r) if lg is not None else simplify(r.T), col(k) if lg is not None else row(k)])
    ax = ip.figures.plot_axes()
    for b in range(r.shape[1]):
        branch = r[:, b]
        ok = np.isfinite(branch)
        ax.plot(branch.real[ok], branch.imag[ok], color=PALETTE[b % len(PALETTE)], linewidth=1.8,
                label="_nolegend_")
    _mark_poles_zeros(ax, G, "#24324A")
    centroid, angles = an.asymptotes(G)
    xlim, ylim = an.rlocus_limits(G, r)
    if gains is not None:
        fin = r[np.isfinite(r)]
        if fin.size:
            xlim = (min(xlim[0], fin.real.min() - 0.5), max(xlim[1], fin.real.max() + 0.5))
            ym = max(abs(ylim[0]), np.abs(fin.imag).max() + 0.5)
            ylim = (-ym, ym)
    ax.axhline(0, color="#B8C7D9", linewidth=0.8, zorder=0)
    ax.axvline(0, color="#B8C7D9", linewidth=0.8, linestyle="--", zorder=0)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_title("Root Locus", fontsize=11, fontweight="bold")
    ax.set_xlabel("Real Axis (seconds$^{-1}$)")
    ax.set_ylabel("Imaginary Axis (seconds$^{-1}$)")
    ip.figures.apply_grid(ax, True)
    ax._hl_rlocus = (G, k, r)
    ax._hl_kind = "rlocus"


@builtin("rlocfind", sig="[K, poles] = rlocfind(G, p)  |  rlocfind(num, den)",
         en="Gain K that places a closed-loop pole at the point p (asks for p if not given)",
         ar="إيجاد الكسب K عند نقطة على المحل الهندسي للجذور", cat=CAT)
def _rlocfind(ip, args, nargout):
    args, _ = expand_legacy(ip, args)
    G = tf_arg(args[0])
    if len(args) > 1:
        p = complex(scalar(args[1]))
    else:
        # MATLAB waits for a mouse click; here the point is typed in.
        if getattr(ip, "on_input", None) is None:
            raise MatlabError("Usage: [K, poles] = rlocfind(G, p)  (p = desired closed-loop pole)")
        txt = ip.on_input("Select a point on the root locus - type it, e.g. -0.33+0.58i : ")
        if txt is None:
            raise MatlabError("rlocfind cancelled.")
        from ..parser import parse
        p = complex(scalar(ip.eval(parse(txt).body[0].expr)))
    nv = np.polyval(G.num, p)
    if abs(nv) < 1e-14:
        raise MatlabError("The selected point is a zero of G(s).")
    K = float(np.real(-np.polyval(G.den, p) / nv)) + 0.0
    poles = an.roots(an._char_poly(G.num, G.den, K))
    if nargout == 0:
        ip.write(f"selected_point = {p.real:.4f} {'+' if p.imag >= 0 else '-'} {abs(p.imag):.4f}i\n"
                 f"K = {K:.5g}\n")
        return np.array([[K]])
    return Multi([np.array([[K]]), simplify(col(poles))])


@builtin("initial", sig="initial(sys, x0)  |  [y, t, x] = initial(sys, x0, t)  |  initial(A, B, C, D, x0)",
         en="Free response of a state-space model from the initial state x0",
         ar="الاستجابة الحرة من الشروط الابتدائية", cat=CAT)
def _initial(ip, args, nargout):
    args, lg = expand_legacy(ip, args)
    if len(args) < 2:
        raise MatlabError("Usage: initial(sys, x0) or initial(A, B, C, D, x0)")
    G = tf_arg(args[0])
    if lg is not None and lg[0] == "ss":
        rest = list(lg[2])
        x0 = rest[0]
        extra = rest[1:]
    else:
        x0 = args[1]
        extra = [a for a in args[2:] if not isinstance(a, TransferFunction)]
    A, B, C, D, iu, _ = _ss_of(G)
    x0 = np.real(vector(x0)).astype(float)
    tfinal, tvec = _time_arg(extra)
    poles = np.linalg.eigvals(np.atleast_2d(A))
    t = tvec if tvec is not None else an.auto_time(poles, tfinal)
    try:
        y, x = an.ss_time_response(A, B, C, D, "initial", t, iu, x0=x0)
    except ValueError as e:
        raise MatlabError(str(e))
    if getattr(G, "ss", None) is None:
        y = y[:, :1]
    if nargout:
        return Multi([y, x, col(t)] if lg is not None else [y, col(t), x])
    ax = ip.figures.plot_axes()
    for j in range(y.shape[1]):
        ax.plot(t, y[:, j], label=f"y{j + 1}" if y.shape[1] > 1 else "_nolegend_",
                **_style_kwargs(None, j))
    ax.set_xlim(t[0], t[-1])
    ax.axhline(0, color="#B8C7D9", linewidth=0.8)
    _finish(ip, ax, "Response to Initial Conditions", "Time (seconds)", "Amplitude", [[G, None, None]])
    if y.shape[1] > 1:
        ax.legend(fontsize=8)


@builtin("zntune", sig="[Kp, Ti, Td] = zntune(G, 'PID')  |  zntune(G, 'PI', 1)",
         en="Ziegler-Nichols PID tuning (method 2: critical gain; method 1: S-shaped step response)",
         ar="ضبط متحكم PID بطريقة زيغلر-نيكولز (الفصل العاشر من كتاب Ogata)", cat=CAT)
def _zntune(ip, args, nargout):
    G = tf_arg(args[0])
    kind = (args[1] if len(args) > 1 and isinstance(args[1], str) else "PID").upper()
    if kind not in ("P", "PI", "PID"):
        raise MatlabError("Controller type must be 'P', 'PI' or 'PID'.")
    method = int_arg(args[2]) if len(args) > 2 else None
    lines = []
    if method in (None, 2):
        Kcr, Pcr = an.zn_ultimate(G)
        if Kcr is None and method == 2:
            raise MatlabError("Method 2 needs a system whose closed loop K*G becomes unstable "
                              "(the root locus must cross the jw axis).")
        if Kcr is not None:
            method = 2
            Kp, Ti, Td = an.zn_table(kind, 2, Kcr, Pcr)
            lines.append(f"  Ziegler-Nichols method 2 (critical gain), Ogata ch. 10\n"
                         f"  Kcr = {Kcr:.5g}   Pcr = {Pcr:.5g} s")
    if method in (None, 1):
        K, L, T = an.zn_step_parameters(G)
        if K is None or L is None or L <= 0:
            raise MatlabError("Method 1 needs an S-shaped (non-oscillatory, delayed) step response.")
        method = 1
        Kp, Ti, Td = an.zn_table(kind, 1, L, T)
        lines.append(f"  Ziegler-Nichols method 1 (step response), Ogata ch. 10\n"
                     f"  L = {L:.5g} s   T = {T:.5g} s   (K = {K:.4g})")
    Ki = 0.0 if np.isinf(Ti) else Kp / Ti
    Kd = Kp * Td
    if nargout:
        return Multi([np.array([[Kp]]), np.array([[Ti]]), np.array([[Td]]),
                      pid(Kp, Ki, Kd)])
    lines.append(f"  {kind}:  Kp = {Kp:.5g}   Ti = {'Inf' if np.isinf(Ti) else f'{Ti:.5g}'}   Td = {Td:.5g}")
    lines.append(f"       ->  Ki = Kp/Ti = {Ki:.5g}   Kd = Kp*Td = {Kd:.5g}")
    lines.append(f"  Use:  C = pid({Kp:.5g}, {Ki:.5g}, {Kd:.5g});  T = feedback(C*G, 1);")
    ip.write("\n" + "\n".join(lines) + "\n\n")


@builtin("acker", sig="K = acker(A, B, p)", en="Pole placement by Ackermann's formula (single input)",
         ar="وضع الأقطاب بصيغة أكرمان", cat=CAT)
def _acker(ip, args, nargout):
    A = num_arg(args[0]).astype(float)
    B = num_arg(args[1]).astype(float)
    p = vector(args[2])
    n = A.shape[0]
    Mc = np.hstack([np.linalg.matrix_power(A, k) @ B for k in range(n)])
    if np.linalg.matrix_rank(Mc) < n:
        raise MatlabError("The system is not controllable.")
    coeffs = np.real(np.poly(p))
    phi = sum(c * np.linalg.matrix_power(A, n - k) for k, c in enumerate(coeffs))
    e = np.zeros((1, n))
    e[0, -1] = 1
    return e @ np.linalg.inv(Mc) @ phi


@builtin("place", sig="K = place(A, B, p)", en="Pole placement (robust method)",
         ar="وضع الأقطاب", cat=CAT)
def _place(ip, args, nargout):
    from scipy.signal import place_poles
    A = num_arg(args[0]).astype(float)
    B = num_arg(args[1]).astype(float)
    res = place_poles(A, B, vector(args[2]))
    return np.atleast_2d(res.gain_matrix)


@builtin("lqr", sig="[K, P, E] = lqr(A, B, Q, R)", en="Linear-quadratic regulator design",
         ar="المنظم الخطي التربيعي الأمثل", cat=CAT)
def _lqr(ip, args, nargout):
    from scipy.linalg import solve_continuous_are
    A, B, Q, R = (num_arg(a).astype(float) for a in args[:4])
    P = solve_continuous_are(A, B, Q, R)
    K = np.linalg.solve(R, B.T @ P)
    E = np.linalg.eigvals(A - B @ K)
    return Multi([np.atleast_2d(K), P, simplify(col(E))])


@builtin("ctrb", sig="Co = ctrb(A, B)", en="Controllability matrix", ar="مصفوفة قابلية التحكم", cat=CAT)
def _ctrb(ip, args, nargout):
    A = num_arg(args[0]).astype(float)
    B = num_arg(args[1]).astype(float)
    return np.hstack([np.linalg.matrix_power(A, k) @ B for k in range(A.shape[0])])


@builtin("obsv", sig="Ob = obsv(A, C)", en="Observability matrix", ar="مصفوفة قابلية الملاحظة", cat=CAT)
def _obsv(ip, args, nargout):
    A = num_arg(args[0]).astype(float)
    C = num_arg(args[1]).astype(float)
    return np.vstack([C @ np.linalg.matrix_power(A, k) for k in range(A.shape[0])])


@builtin("rlocinfo", sig="rlocinfo(G)", en="Root-locus construction rules: asymptotes, breakaway points, jw crossings",
         ar="قواعد رسم المحل الهندسي: الخطوط المقاربة ونقاط الانفصال والتقاطع مع المحور التخيلي", cat=CAT)
def _rlocinfo(ip, args, nargout):
    G = tf_arg(args[0])
    p, z = G.poles(), G.zeros()
    centroid, angles = an.asymptotes(G)
    bp, bk = an.breakaway_points(G)
    lines = ["", f"  Open-loop poles : {', '.join(_cfmt(x) for x in p) or '-'}",
             f"  Open-loop zeros : {', '.join(_cfmt(x) for x in z) or '-'}",
             f"  Branches        : {len(p)}   (n - m = {len(p) - len(z)} go to infinity)"]
    if centroid is not None:
        lines.append(f"  Asymptote centroid sigma_a = {centroid:.4g}")
        lines.append(f"  Asymptote angles           = {', '.join(f'{a:.4g}' for a in angles)} deg")
    for s, k in zip(bp, bk):
        lines.append(f"  Breakaway/break-in point s = {s:.4g}   (K = {k:.4g})")
    for k, wc in an.imag_axis_crossings(G):
        lines.append(f"  jw-axis crossing at s = +/-j{wc:.4g}   (K = {k:.4g})")
    ip.write("\n".join(lines) + "\n\n")


@builtin("pzmap", sig="pzmap(G)  |  [p, z] = pzmap(G)", en="Pole-zero map (x = poles, o = zeros)",
         ar="خريطة الأقطاب والأصفار", cat=CAT)
def _pzmap(ip, args, nargout):
    systems, _ = _split_systems(ip, args)
    if nargout:
        G = systems[0][0]
        z = G.zeros()
        return Multi([simplify(col(G.poles())), simplify(col(z)) if z.size else np.zeros((0, 1))])
    ax = ip.figures.plot_axes()
    allpts = []
    for k, (G, spec, name) in enumerate(systems):
        color = PALETTE[k % len(PALETTE)]
        _mark_poles_zeros(ax, G, color)
        allpts.extend(list(G.poles()) + list(G.zeros()))
    allpts = np.array(allpts + [0j])
    span = max(np.ptp(allpts.real), np.ptp(allpts.imag), 1.0)
    ax.set_xlim(allpts.real.min() - 0.3 * span, max(allpts.real.max(), 0) + 0.3 * span)
    ym = max(np.abs(allpts.imag).max(), 0.5) + 0.3 * span
    ax.set_ylim(-ym, ym)
    ax.axhline(0, color="#B8C7D9", linewidth=0.8)
    ax.axvline(0, color="#B8C7D9", linewidth=0.8, linestyle="--")
    _finish(ip, ax, "Pole-Zero Map", "Real Axis (seconds$^{-1}$)", "Imaginary Axis (seconds$^{-1}$)", systems)


@builtin("sgrid", sig="sgrid  |  sgrid(zeta, wn)", en="Damping-ratio lines and natural-frequency circles on an s-plane plot",
         ar="خطوط نسبة الإخماد ودوائر التردد الطبيعي", cat=CAT)
def _sgrid(ip, args, nargout):
    ax = ip.figures.gca()
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    R = 1.5 * max(abs(xlim[0]), abs(xlim[1]), abs(ylim[0]), abs(ylim[1]))
    zetas = vector(args[0]) if args and not isinstance(args[0], str) else \
        np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    if len(args) > 1:
        wns = vector(args[1])
    else:
        step = 10 ** np.floor(np.log10(R / 2)) if R > 0 else 1
        wns = np.arange(step, R, step)
    for z in zetas:
        th = np.arccos(np.clip(z, -1, 1))
        for sgn in (1, -1):
            ax.plot([0, -R * np.cos(th)], [0, sgn * R * np.sin(th)], color="#9FB3C8",
                    linestyle=":", linewidth=0.9, label="_nolegend_", zorder=0)
        ax.text(-0.92 * min(R, abs(xlim[0])) * np.cos(th), 0.92 * min(R, abs(xlim[0])) * np.sin(th),
                f"{z:g}", fontsize=7, color="#6C8299", clip_on=True)
    t = np.linspace(np.pi / 2, 3 * np.pi / 2, 100)
    for w in wns:
        ax.plot(w * np.cos(t), w * np.sin(t), color="#9FB3C8", linestyle=":", linewidth=0.9,
                label="_nolegend_", zorder=0)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ip.figures.touch()
