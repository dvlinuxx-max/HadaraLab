"""Numerical analysis of transfer functions: time response, frequency
response, stability margins, root locus and the Routh-Hurwitz array.

The step-info and root-locus heuristics follow the approach used by
python-control (and Ogata, Modern Control Engineering).
"""

import numpy as np
from scipy import signal
from scipy.optimize import brentq

from .tf import TransferFunction, clean_poly, roots

_EPS = 1e-9


# ---------------------------------------------------------------------------
# Time domain
# ---------------------------------------------------------------------------

def auto_time(G, tfinal=None, npts=None):
    """Pick a sensible simulation horizon and time vector for G.

    G may be a TransferFunction or an array of poles (for state-space models).
    """
    p = np.asarray(G, dtype=complex) if isinstance(G, np.ndarray) else G.poles()
    nonzero = p[np.abs(p) > 1e-8]
    has_integrator = len(nonzero) < len(p)
    if tfinal is None:
        tfinal = 0.0
        if nonzero.size:
            re = nonzero.real
            unstable = re > 1e-8
            stable = re < -1e-8
            marginal = ~unstable & ~stable
            if np.any(stable):
                tfinal = max(tfinal, np.log(1000) / np.min(-re[stable]))
            if np.any(marginal):
                w = np.min(np.abs(nonzero.imag[marginal]))
                tfinal = max(tfinal, 5 * 2 * np.pi / w)
            if np.any(unstable):
                tfinal = max(tfinal, 4.0 / np.max(re[unstable]))
        if tfinal == 0.0:
            tfinal = 10.0
        if has_integrator:
            tfinal = max(tfinal, 10.0)
        tfinal = float(np.clip(tfinal, 1e-3, 1e5))
        # round to a "nice" number like MATLAB plots do
        mag = 10 ** np.floor(np.log10(tfinal))
        tfinal = float(np.ceil(tfinal / mag * 2) / 2 * mag)
    if npts is None:
        dt = tfinal / 1000.0
        if nonzero.size:
            wmax = np.max(np.abs(nonzero.imag)) if np.any(np.abs(nonzero.imag) > 0) else 0
            if wmax > 0:
                dt = min(dt, 2 * np.pi / wmax / 40)
        npts = int(np.clip(tfinal / dt, 300, 20000))
    return np.linspace(0, tfinal, npts + 1)


def _check_proper(G, what):
    if not G.is_proper():
        raise ValueError(f"{what} is not available for improper (non-causal) "
                         "transfer functions (numerator order > denominator order).")


def step_response(G, t=None):
    _check_proper(G, "Step response")
    if t is None:
        t = auto_time(G)
    t = np.asarray(t, dtype=float).ravel()
    if G.is_static():
        return t, np.full_like(t, G.num[0] / G.den[0])
    _, y, _ = signal.lsim((G.num, G.den), np.ones_like(t), t)
    return t, np.real(y)


def impulse_response(G, t=None):
    _check_proper(G, "Impulse response")
    if t is None:
        t = auto_time(G)
    t = np.asarray(t, dtype=float).ravel()
    if G.is_static():
        return t, np.zeros_like(t)
    # strictly proper part only (a feedthrough term would be a Dirac delta)
    q, r = np.polydiv(G.num, G.den) if len(G.num) == len(G.den) else (0, G.num)
    r = clean_poly(r)
    if np.all(r == 0):
        return t, np.zeros_like(t)
    _, y = signal.impulse((r, G.den), T=t)
    return t, np.real(y)


def lsim_response(G, u, t):
    _check_proper(G, "lsim")
    t = np.asarray(t, dtype=float).ravel()
    u = np.asarray(u, dtype=float).ravel()
    if u.size == 1:
        u = np.full_like(t, u[0])
    if u.size != t.size:
        raise ValueError("Input signal u and time vector t must have the same length.")
    if G.is_static():
        return t, u * G.num[0] / G.den[0]
    _, y, _ = signal.lsim((G.num, G.den), u, t)
    return t, np.real(y)


def ss_time_response(A, B, C, D, kind, t, iu=0, x0=None, u=None):
    """Time response of a state-space model for input number iu.

    kind: 'step', 'impulse', 'initial' (free response from x0) or 'lsim'.
    Returns (y, x) with one column per output / state.
    """
    A = np.atleast_2d(np.asarray(A, float))
    B = np.atleast_2d(np.asarray(B, float))
    C = np.atleast_2d(np.asarray(C, float))
    n = A.shape[0]
    D = np.asarray(D, float)
    D = np.zeros((C.shape[0], B.shape[1])) if D.size == 0 else (
        np.full((C.shape[0], B.shape[1]), D.ravel()[0]) if D.size == 1 else np.atleast_2d(D))
    Bi = B[:, iu:iu + 1]
    Di = D[:, iu:iu + 1]
    t = np.asarray(t, float).ravel()
    X0 = np.zeros(n)
    U = np.zeros_like(t)
    if kind == "step":
        U = np.ones_like(t)
    elif kind == "impulse":
        X0 = Bi[:, 0].copy()
        Di = np.zeros_like(Di)
    elif kind == "initial":
        X0 = np.asarray(x0, float).ravel()
        if X0.size != n:
            raise ValueError(f"The initial state must have {n} elements.")
    elif kind == "lsim":
        U = np.asarray(u, float).ravel()
        if x0 is not None:
            X0 = np.asarray(x0, float).ravel()
    _, y, x = signal.lsim((A, Bi, C, Di), U, t, X0=X0)
    return np.real(y).reshape(len(t), -1), np.real(x).reshape(len(t), -1)


def step_info(t, y, yfinal=None, settling=0.02, rise=(0.1, 0.9)):
    t = np.asarray(t, float).ravel()
    y = np.asarray(y, float).ravel()
    if yfinal is None:
        yfinal = y[-1]
    info = dict(RiseTime=np.nan, TransientTime=np.nan, SettlingTime=np.nan,
                SettlingMin=np.nan, SettlingMax=np.nan, Overshoot=np.nan,
                Undershoot=np.nan, Peak=np.nan, PeakTime=np.nan)
    if not np.isfinite(yfinal) or abs(yfinal) < 1e-14:
        peak_i = int(np.argmax(np.abs(y)))
        info["Peak"] = float(np.abs(y[peak_i]))
        info["PeakTime"] = float(t[peak_i])
        return info
    sgn = np.sign(yfinal)
    lo = np.nonzero(sgn * (y - rise[0] * yfinal) >= 0)[0]
    hi = np.nonzero(sgn * (y - rise[1] * yfinal) >= 0)[0]
    if lo.size and hi.size:
        info["RiseTime"] = float(t[hi[0]] - t[lo[0]])
    outside = np.nonzero(np.abs(y / yfinal - 1) >= settling)[0]
    k = 0 if outside.size == 0 else outside[-1] + 1
    if k < len(t):
        # interpolate the exact crossing time of the settling band
        if k > 0:
            y0, y1 = y[k - 1], y[k]
            band = yfinal * (1 + settling * np.sign(y0 - yfinal))
            if y1 != y0:
                frac = np.clip((band - y0) / (y1 - y0), 0, 1)
                info["SettlingTime"] = float(t[k - 1] + frac * (t[k] - t[k - 1]))
            else:
                info["SettlingTime"] = float(t[k])
        else:
            info["SettlingTime"] = 0.0
        info["TransientTime"] = info["SettlingTime"]
    start = hi[0] if hi.size else 0
    info["SettlingMin"] = float(min(y[start:].min(), yfinal))
    info["SettlingMax"] = float(max(y[start:].max(), yfinal))
    y_os = (sgn * y).max()
    dy = abs(y_os) - abs(yfinal)
    info["Overshoot"] = float(100 * dy / abs(yfinal)) if dy > 0 else 0.0
    y_us = (sgn * y).min()
    info["Undershoot"] = float(-100 * y_us / abs(yfinal)) if y_us < 0 else 0.0
    peak_i = int(np.argmax(np.abs(y)))
    info["Peak"] = float(np.abs(y[peak_i]))
    info["PeakTime"] = float(t[peak_i])
    return info


def system_step_info(G):
    p = G.poles()
    # unstable or marginally stable (integrator, undamped oscillation): no settling
    if np.any(p.real > -1e-9):
        return step_info([0], [np.inf], np.inf)
    t, y = step_response(G)
    yfinal = G.dcgain()
    if not np.isfinite(yfinal):
        yfinal = None
    # make sure the response actually settled inside the window
    t, y = _extend_until_settled(G, t, y, yfinal)
    return step_info(t, y, yfinal)


def _extend_until_settled(G, t, y, yfinal):
    if yfinal is None or yfinal == 0:
        return t, y
    for _ in range(4):
        if abs(y[-1] / yfinal - 1) < 0.005:
            break
        t = auto_time(G, tfinal=t[-1] * 2, npts=len(t) * 2)
        t, y = step_response(G, t)
    return t, y


def steady_state_errors(G):
    """Static error constants and steady-state errors for a unity feedback
    loop with open-loop transfer function G (Ogata, chapter 5)."""
    num, den = G.num, G.den
    # count poles at the origin (system type)
    d = den.copy()
    n_type = 0
    while len(d) > 1 and abs(d[-1]) < 1e-12:
        d = d[:-1]
        n_type += 1
    k_rest = np.polyval(num, 0) / np.polyval(d, 0)
    Kp = np.inf if n_type >= 1 else k_rest
    Kv = np.inf if n_type >= 2 else (k_rest if n_type == 1 else 0.0)
    Ka = np.inf if n_type >= 3 else (k_rest if n_type == 2 else 0.0)

    def err(k, extra=0):
        if np.isinf(k):
            return 0.0
        if k == 0:
            return np.inf
        return 1.0 / (extra + k)

    return dict(Type=float(n_type), Kp=float(Kp), Kv=float(Kv), Ka=float(Ka),
                ess_step=float(err(Kp, 1)), ess_ramp=float(err(Kv)),
                ess_parabola=float(err(Ka)))


def damp(G):
    p = G.poles()
    wn = np.abs(p)
    zeta = np.where(wn > 0, -p.real / np.where(wn > 0, wn, 1), -1.0)
    tau = np.where(p.real != 0, -1 / np.where(p.real != 0, p.real, 1), np.inf)
    order = np.argsort(wn)
    return p[order], wn[order], zeta[order], tau[order]


# ---------------------------------------------------------------------------
# Frequency domain
# ---------------------------------------------------------------------------

def auto_freq(G, n=1000):
    pz = np.concatenate([G.poles(), G.zeros()])
    corners = np.abs(pz[np.abs(pz) > 1e-8])
    if corners.size == 0:
        lo, hi = -1, 2
    else:
        lo = np.floor(np.log10(corners.min())) - 1
        hi = np.ceil(np.log10(corners.max())) + 1
        if hi - lo < 3:
            hi = lo + 3
    return np.logspace(lo, hi, n)


def freq_response(G, w):
    w = np.asarray(w, dtype=float).ravel()
    H = G(1j * w)
    mag = np.abs(H)
    phase = np.unwrap(np.angle(H)) * 180 / np.pi
    # Shift the phase branch so the low-frequency value matches the
    # textbook expectation (e.g. -90 deg for a single integrator).
    nz0 = int(np.sum(np.abs(G.zeros()) < 1e-8))
    np0 = int(np.sum(np.abs(G.poles()) < 1e-8))
    expected = 90.0 * (nz0 - np0)
    if phase.size:
        k = np.round((phase[0] - expected) / 360.0)
        # keep a negative low-frequency gain at -180 rather than +180
        phase = phase - 360.0 * k
        if phase[0] > expected + 180 - 1e-6:
            phase -= 360.0
    return mag, phase, w


def margins(G):
    """Gain margin (absolute), phase margin (deg), and their frequencies.

    Returns (Gm, Pm, Wcg, Wcp) like MATLAB's margin(). Gm is the factor the
    gain can grow by before instability (inf if the phase never hits -180).
    """
    w = auto_freq(G, 4000)
    w = np.logspace(np.log10(w[0]) - 1, np.log10(w[-1]) + 1, 6000)
    mag, phase, w = freq_response(G, w)
    lw = np.log10(w)

    def interp_at(x_target, xs, ys):
        return np.interp(x_target, xs, ys)

    # Gain crossover: |G| = 1
    Pm, Wcp = np.inf, np.nan
    f = np.log10(np.maximum(mag, 1e-300))
    idx = np.nonzero(np.sign(f[:-1]) * np.sign(f[1:]) < 0)[0]
    for i in idx:
        try:
            lwc = brentq(lambda x: np.log10(abs(G(1j * 10 ** x))), lw[i], lw[i + 1])
        except ValueError:
            lwc = lw[i]
        ph = interp_at(lwc, lw, phase)
        pm = 180.0 + ph
        pm = (pm + 180.0) % 360.0 - 180.0
        if abs(pm) < abs(Pm):
            Pm, Wcp = pm, 10 ** lwc

    # Phase crossover: phase = -180 + k*360
    Gm, Wcg = np.inf, np.nan
    kmin = int(np.floor(phase.min() / 360.0)) - 1
    kmax = int(np.ceil(phase.max() / 360.0)) + 1
    for kk in range(kmin, kmax + 1):
        target = -180.0 + 360.0 * kk
        g = phase - target
        idx = np.nonzero(np.sign(g[:-1]) * np.sign(g[1:]) < 0)[0]
        for i in idx:
            frac = g[i] / (g[i] - g[i + 1])
            lwc = lw[i] + frac * (lw[i + 1] - lw[i])
            m = abs(G(1j * 10 ** lwc))
            if m < 1e-300:
                continue
            gm = 1.0 / m
            # MATLAB reports the margin closest to 0 dB
            if np.isinf(Gm) or abs(np.log10(gm)) < abs(np.log10(Gm)):
                Gm, Wcg = gm, 10 ** lwc
    return float(Gm), float(Pm), float(Wcg), float(Wcp)


def nyquist_data(G, w=None):
    if w is None:
        w = auto_freq(G, 2000)
        w = np.logspace(np.log10(w[0]) - 1, np.log10(w[-1]) + 1, 3000)
    H = G(1j * np.asarray(w))
    return H, w


# ---------------------------------------------------------------------------
# Root locus
# ---------------------------------------------------------------------------

def _char_poly(num, den, k):
    n = max(len(num), len(den))
    a = np.concatenate([np.zeros(n - len(den)), den])
    b = np.concatenate([np.zeros(n - len(num)), num])
    return a + k * b


def _sort_roots(rows):
    """Reorder roots row-by-row so each branch is continuous."""
    out = np.zeros_like(rows)
    out[0] = rows[0]
    for n in range(1, len(rows)):
        prev = out[n - 1]
        available = list(range(len(prev)))
        for r in rows[n]:
            j = int(np.argmin(np.abs(r - prev[available])))
            out[n, available.pop(j)] = r
    return out


def _roots_for_gains(num, den, gains):
    order = max(len(num), len(den)) - 1
    res = np.empty((len(gains), order), dtype=complex)
    for i, k in enumerate(gains):
        r = np.roots(_char_poly(num, den, k))
        if len(r) < order:  # leading coefficient vanished at this gain
            r = np.concatenate([r, np.full(order - len(r), np.inf + 0j)])
        res[i] = r
    return res


def breakaway_points(G):
    """Real breakaway / break-in points with their (positive) gains."""
    num, den = G.num, G.den
    # dK/ds = 0  ->  num*den' - den*num' = 0
    p = np.polysub(np.polymul(num, np.polyder(den)), np.polymul(den, np.polyder(num)))
    pts, gains = [], []
    for s in roots(p) if len(clean_poly(p)) > 1 else []:
        if abs(np.imag(s)) > 1e-6:
            continue
        s = float(np.real(s))
        nv = np.polyval(num, s)
        if abs(nv) < 1e-12:
            continue
        k = -np.polyval(den, s) / nv
        if np.isreal(k) and np.real(k) > 0:
            pts.append(s)
            gains.append(float(np.real(k)))
    return np.array(pts), np.array(gains)


def imag_axis_crossings(G):
    """Gains and frequencies where closed-loop poles cross the jw axis."""
    num, den = G.num, G.den
    out = []
    # 1 + K G(jw) = 0  ->  K = -den(jw)/num(jw) must be real & positive
    w = np.logspace(-4, 4, 20000)
    with np.errstate(all="ignore"):
        val = -np.polyval(den, 1j * w) / np.polyval(num, 1j * w)
    im = val.imag
    idx = np.nonzero(np.sign(im[:-1]) * np.sign(im[1:]) < 0)[0]
    for i in idx:
        try:
            wc = brentq(lambda x: (-np.polyval(den, 1j * x) / np.polyval(num, 1j * x)).imag,
                        w[i], w[i + 1])
        except ValueError:
            continue
        k = (-np.polyval(den, 1j * wc) / np.polyval(num, 1j * wc)).real
        if k > 0:
            out.append((float(k), float(wc)))
    return out


def rlocus_data(G, gains=None):
    num, den = G.num, G.den
    if np.all(num == 0):
        raise ValueError("Root locus needs a non-zero numerator.")
    poles = G.poles()
    zeros = G.zeros()
    if gains is not None:
        gains = np.sort(np.asarray(gains, float).ravel())
        rts = _sort_roots(_roots_for_gains(num, den, gains))
        return gains, rts

    # Scale of the plot = spread of the open-loop singularities
    pts = np.concatenate([poles, zeros, [0]])
    R = max(1.0, float(np.max(np.abs(pts))))
    # Find a gain big enough that the free branches are far away
    n_inf = len(poles) - len(zeros)
    k = 1e-3 * abs(den[0] / num[0]) if num[0] != 0 else 1e-3
    k = max(k, 1e-6)
    kmax = k
    for _ in range(200):
        r = np.roots(_char_poly(num, den, kmax))
        if n_inf > 0:
            if np.max(np.abs(r)) > 4 * R:
                break
        else:
            if zeros.size and np.max(np.min(np.abs(r[:, None] - zeros[None, :]), axis=1)) < 0.01 * R:
                break
        kmax *= 1.6
    _, kb = breakaway_points(G)
    kc = [k for k, _ in imag_axis_crossings(G)]
    extra = np.concatenate([kb, kc]) if (len(kb) or len(kc)) else np.array([])
    kmax = max(kmax, 2 * extra.max()) if extra.size else kmax
    gains = np.unique(np.concatenate([
        [0.0],
        kmax * np.logspace(-6, 0, 250),
        np.linspace(0, kmax, 250),
        extra,
    ]))
    rts = _sort_roots(_roots_for_gains(num, den, gains))

    # Refine where consecutive points jump too far apart
    tol = 0.02 * R
    for _ in range(6):
        jumps = np.max(np.abs(np.diff(rts, axis=0)), axis=1)
        bad = np.nonzero(jumps > tol)[0]
        if bad.size == 0 or len(gains) > 6000:
            break
        new = []
        for i in bad:
            new.extend(np.linspace(gains[i], gains[i + 1], 6)[1:-1])
        gains = np.unique(np.concatenate([gains, new]))
        rts = _sort_roots(_roots_for_gains(num, den, gains))
    return gains, rts


def rlocus_limits(G, rts):
    poles, zeros = G.poles(), G.zeros()
    bp, _ = breakaway_points(G)
    pts = np.concatenate([poles, zeros, bp.astype(complex), [0]])
    for k, wc in imag_axis_crossings(G):
        pts = np.concatenate([pts, [1j * wc, -1j * wc]])
    re, im = pts.real, pts.imag
    span = max(re.max() - re.min(), im.max() - im.min(), 1.0)
    xlo, xhi = re.min() - 0.6 * span, re.max() + 0.6 * span
    ylo, yhi = im.min() - 0.6 * span, im.max() + 0.6 * span
    ymax = max(abs(ylo), abs(yhi))
    return (xlo, xhi), (-ymax, ymax)


def asymptotes(G):
    p, z = G.poles(), G.zeros()
    n = len(p) - len(z)
    if n <= 0:
        return None, []
    centroid = float(np.real((np.sum(p) - np.sum(z)) / n))
    angles = [(2 * q + 1) * 180.0 / n for q in range(n)]
    return centroid, angles


# ---------------------------------------------------------------------------
# Ziegler-Nichols tuning (Ogata, chapter 10)
# ---------------------------------------------------------------------------

def zn_ultimate(G):
    """Second method: critical gain Kcr and period Pcr (jw-axis crossing)."""
    cr = imag_axis_crossings(G)
    if not cr:
        return None, None
    k, w = min(cr)
    return k, 2 * np.pi / w


def zn_step_parameters(G):
    """First method: delay L and time constant T from the S-shaped step response."""
    t, y = step_response(G, auto_time(G, npts=4000))
    K = y[-1]
    dy = np.gradient(y, t)
    i = int(np.argmax(dy))
    slope = dy[i]
    if slope <= 0 or K <= 0:
        return None, None, None
    L = t[i] - y[i] / slope            # tangent crosses y = 0
    T = K / slope                      # tangent rises from 0 to K in T seconds
    return K, max(L, 0.0), T


def zn_table(kind, method, a, b):
    """Return (Kp, Ti, Td). method 1: a=L, b=T ; method 2: a=Kcr, b=Pcr."""
    inf = np.inf
    if method == 1:
        L, T = a, b
        return {"P": (T / L, inf, 0.0), "PI": (0.9 * T / L, L / 0.3, 0.0),
                "PID": (1.2 * T / L, 2 * L, 0.5 * L)}[kind]
    Kcr, Pcr = a, b
    return {"P": (0.5 * Kcr, inf, 0.0), "PI": (0.45 * Kcr, Pcr / 1.2, 0.0),
            "PID": (0.6 * Kcr, 0.5 * Pcr, 0.125 * Pcr)}[kind]


# ---------------------------------------------------------------------------
# Routh-Hurwitz
# ---------------------------------------------------------------------------

def routh_array(coeffs, eps=1e-6):
    """Build the Routh array. Returns (table, notes, sign_changes)."""
    c = clean_poly(np.real(np.asarray(coeffs, dtype=complex)))
    n = len(c) - 1
    if n < 1:
        raise ValueError("The polynomial must be at least first order.")
    cols = (n + 2) // 2
    T = np.zeros((n + 1, cols))
    r0 = c[0::2]
    r1 = c[1::2]
    T[0, :len(r0)] = r0
    T[1, :len(r1)] = r1
    notes = []
    for i in range(1, n + 1):
        if i >= 2:
            a, b = T[i - 2], T[i - 1]
            for j in range(cols - 1):
                T[i, j] = (b[0] * a[j + 1] - a[0] * b[j + 1]) / b[0]
        row = T[i]
        if np.all(np.abs(row) < 1e-12) and i <= n:
            # Whole row of zeros: use the derivative of the auxiliary polynomial
            prev = T[i - 1]
            order = n - (i - 1)
            powers = np.arange(order, -1, -2)
            aux = prev[:len(powers)]
            deriv = (aux * powers)[powers > 0]
            T[i, :] = 0
            T[i, :len(deriv)] = deriv[:cols]
            aux_poly = np.zeros(order + 1)
            aux_poly[::2] = aux
            notes.append(("zero_row", i, aux_poly))
            if np.all(np.abs(T[i]) < 1e-12):
                break
        elif abs(row[0]) < 1e-12:
            T[i, 0] = eps
            notes.append(("zero_first", i, None))
    first = T[:, 0]
    signs = np.sign(first[np.abs(first) > 1e-14])
    changes = int(np.sum(signs[:-1] * signs[1:] < 0))
    return T, notes, changes
