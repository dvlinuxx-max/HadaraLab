"""Continuous-time SISO transfer function  G(s) = num(s) / den(s).

Polynomials are stored as 1-D numpy arrays, highest power first
(the same convention MATLAB uses: [1 3 2] means s^2 + 3s + 2).
"""

import numpy as np

_TOL = 1e-10


def clean_poly(p):
    """Return p as a 1-D float/complex array without leading zeros."""
    p = np.atleast_1d(np.asarray(p)).ravel()
    if p.dtype.kind not in "fc":
        p = p.astype(float)
    if np.iscomplexobj(p):
        scale = max(1.0, float(np.max(np.abs(p)))) if p.size else 1.0
        if np.all(np.abs(p.imag) <= 1e-9 * scale):
            p = p.real.copy()
    nz = np.flatnonzero(p != 0)
    if nz.size == 0:
        return np.array([0.0])
    return p[nz[0]:].copy()


def poly_add(a, b):
    n = max(len(a), len(b))
    a = np.concatenate([np.zeros(n - len(a)), a])
    b = np.concatenate([np.zeros(n - len(b)), b])
    return clean_poly(a + b)


def poly_from_roots(r):
    if len(r) == 0:
        return np.array([1.0])
    return clean_poly(np.poly(r))


def roots(p):
    p = clean_poly(p)
    if p.size <= 1:
        return np.array([])
    r = np.roots(p)
    # snap tiny imaginary/real parts so printed results look clean
    scale = np.maximum(1, np.abs(r))
    re = np.where(np.abs(r.real) < 1e-9 * scale, 0.0, r.real)
    im = np.where(np.abs(r.imag) < 1e-9 * scale, 0.0, r.imag)
    r = re + 1j * im
    if np.all(im == 0):
        r = re
    return r


def fmt_coef(c):
    """Coefficient formatting close to MATLAB's display."""
    if isinstance(c, complex) or np.iscomplexobj(c):
        return f"({c.real:.4g}{c.imag:+.4g}i)"
    if not np.isfinite(c):
        return "Inf" if c > 0 else ("-Inf" if c < 0 else "NaN")
    if abs(c - round(c)) < 1e-9 * max(1, abs(c)) and abs(c) < 1e10:
        return str(int(round(c)))
    return f"{c:.4g}"


def poly_to_str(p, var="s"):
    p = clean_poly(p)
    n = len(p) - 1
    terms = []
    for k, c in enumerate(p):
        power = n - k
        if c == 0:
            continue
        neg = (not np.iscomplexobj(c)) and c < 0
        mag = -c if neg else c
        if power == 0:
            body = fmt_coef(mag)
        else:
            vp = var if power == 1 else f"{var}^{power}"
            body = vp if np.isclose(mag, 1) and not np.iscomplexobj(mag) \
                else f"{fmt_coef(mag)} {vp}"
        if not terms:
            terms.append(("-" if neg else "") + body)
        else:
            terms.append((" - " if neg else " + ") + body)
    return "".join(terms) if terms else "0"


class TransferFunction:
    def __init__(self, num, den=1.0, name=""):
        num = clean_poly(num)
        den = clean_poly(den)
        if den.size == 1 and den[0] == 0:
            raise ValueError("The denominator of a transfer function cannot be zero.")
        self.num = num
        self.den = den
        self.name = name
        # (A, B, C, D) when the model was created with ss(); arithmetic drops it
        self.ss = None

    # -- basic properties ----------------------------------------------------
    @property
    def order(self):
        return len(self.den) - 1

    def poles(self):
        return roots(self.den)

    def zeros(self):
        if np.all(self.num == 0):
            return np.array([])
        return roots(self.num)

    def is_proper(self):
        return len(self.num) <= len(self.den)

    def dcgain(self):
        num, den = self.num, self.den
        # cancel common factors of s (e.g. s*G with a pole at the origin)
        while len(num) > 1 and len(den) > 1 and num[-1] == 0 and den[-1] == 0:
            num, den = num[:-1], den[:-1]
        n0 = np.polyval(num, 0)
        d0 = np.polyval(den, 0)
        if abs(d0) < _TOL:
            return np.inf if abs(n0) > _TOL else np.nan
        return n0 / d0

    def __call__(self, s):
        s = np.asarray(s)
        return np.polyval(self.num, s) / np.polyval(self.den, s)

    def is_static(self):
        return len(self.num) == 1 and len(self.den) == 1

    # -- arithmetic ----------------------------------------------------------
    @staticmethod
    def coerce(x):
        if isinstance(x, TransferFunction):
            return x
        arr = np.asarray(x)
        if arr.size != 1:
            raise ValueError("Only scalars can be combined with transfer functions.")
        return TransferFunction([arr.ravel()[0]], [1.0])

    def __add__(self, other):
        o = TransferFunction.coerce(other)
        if np.array_equal(self.den, o.den):
            return TransferFunction(poly_add(self.num, o.num), self.den)
        num = poly_add(np.polymul(self.num, o.den), np.polymul(o.num, self.den))
        return TransferFunction(num, np.polymul(self.den, o.den))

    __radd__ = __add__

    def __neg__(self):
        return TransferFunction(-self.num, self.den)

    def __sub__(self, other):
        return self + (-TransferFunction.coerce(other))

    def __rsub__(self, other):
        return TransferFunction.coerce(other) + (-self)

    def __mul__(self, other):
        o = TransferFunction.coerce(other)
        return TransferFunction(np.polymul(self.num, o.num), np.polymul(self.den, o.den))

    __rmul__ = __mul__

    def inv(self):
        if np.all(self.num == 0):
            raise ZeroDivisionError("Cannot invert a zero transfer function.")
        return TransferFunction(self.den, self.num)

    def __truediv__(self, other):
        return self * TransferFunction.coerce(other).inv()

    def __rtruediv__(self, other):
        return TransferFunction.coerce(other) * self.inv()

    def __pow__(self, n):
        n_arr = np.asarray(n).ravel()
        if n_arr.size != 1 or n_arr[0] != int(n_arr[0]):
            raise ValueError("Transfer functions can only be raised to integer powers.")
        n = int(n_arr[0])
        result = TransferFunction([1.0], [1.0])
        base = self if n >= 0 else self.inv()
        for _ in range(abs(n)):
            result = result * base
        return result

    # -- display -------------------------------------------------------------
    def normalized(self):
        """Scale so the denominator's leading coefficient is 1."""
        lead = self.den[0]
        return TransferFunction(self.num / lead, self.den / lead, self.name)

    def to_str(self, var="s"):
        n = poly_to_str(self.num, var)
        d = poly_to_str(self.den, var)
        if self.is_static() or (len(self.den) == 1 and self.den[0] == 1):
            if len(self.den) == 1 and self.den[0] != 1:
                return f"  {poly_to_str(self.num / self.den[0], var)}"
            return f"  {n}"
        width = max(len(n), len(d))
        return "\n".join([
            "  " + n.center(width).rstrip(),
            "  " + "-" * width,
            "  " + d.center(width).rstrip(),
        ])

    def __repr__(self):
        return self.to_str()


def minreal(G, tol=1e-6):
    """Cancel common pole/zero pairs."""
    z = list(G.zeros())
    p = list(G.poles())
    k = G.num[0] / G.den[0] if G.num[0] != 0 else 0.0
    changed = True
    while changed:
        changed = False
        for zi in list(z):
            for pi in list(p):
                if abs(zi - pi) <= tol * max(1.0, abs(pi)):
                    z.remove(zi)
                    p.remove(pi)
                    changed = True
                    break
            if changed:
                break
    return TransferFunction(clean_poly(k * poly_from_roots(z)), clean_poly(poly_from_roots(p)))


def zpk(z, p, k):
    z = np.atleast_1d(np.asarray(z, dtype=complex)).ravel()
    p = np.atleast_1d(np.asarray(p, dtype=complex)).ravel()
    num = k * poly_from_roots(z) if z.size else np.array([k], dtype=float)
    den = poly_from_roots(p)
    return TransferFunction(clean_poly(num), clean_poly(den))


def series(*systems):
    out = TransferFunction([1.0], [1.0])
    for s in systems:
        out = out * s
    return out


def parallel(*systems):
    out = TransferFunction([0.0], [1.0])
    for s in systems:
        out = out + s
    return out


def feedback(G, H=1.0, sign=-1):
    """Closed loop  G / (1 - sign*G*H)  (sign=-1 -> negative feedback)."""
    G = TransferFunction.coerce(G)
    H = TransferFunction.coerce(H)
    num = np.polymul(G.num, H.den)
    den = poly_add(np.polymul(G.den, H.den), -sign * np.polymul(G.num, H.num))
    return TransferFunction(num, den)


def pid(Kp, Ki=0.0, Kd=0.0, Tf=0.0):
    """Parallel PID:  Kp + Ki/s + Kd*s  (optionally with derivative filter Tf)."""
    if Tf and Kd:
        # Kp + Ki/s + Kd s/(Tf s + 1)
        return TransferFunction([Kp], [1]) + TransferFunction([Ki], [1, 0]) \
            + TransferFunction([Kd, 0], [Tf, 1])
    if Ki == 0 and Kd == 0:
        return TransferFunction([Kp], [1.0])
    # (Kd s^2 + Kp s + Ki) / s
    if Ki == 0:
        return TransferFunction([Kd, Kp], [1.0])
    return TransferFunction([Kd, Kp, Ki], [1.0, 0.0])


def ss2tf(A, B, C, D):
    from scipy import signal
    num, den = signal.ss2tf(np.atleast_2d(A), np.atleast_2d(B),
                            np.atleast_2d(C), np.atleast_2d(D))
    return TransferFunction(clean_poly(np.round(num[0], 12)), clean_poly(np.round(den, 12)))


def tf2ss(G):
    from scipy import signal
    if not G.is_proper():
        raise ValueError("Cannot convert an improper transfer function to state space.")
    return signal.tf2ss(G.num, G.den)
