"""General 2-D plotting builtins (plot, subplot, hold, grid, labels...)."""

import re

import numpy as np

from . import builtin
from .core import int_arg, num_arg
from ..errors import MatlabError
from ..values import Cell, FunctionHandle, scalar, to_array, vector
from ...control.tf import TransferFunction
from ...graphics import MATLAB_COLORS, PALETTE

CAT = "Plotting"

_LINE_PROPS = {
    "linewidth": "linewidth", "color": "color", "markersize": "markersize",
    "marker": "marker", "linestyle": "linestyle", "displayname": "label",
    "markerfacecolor": "markerfacecolor", "markeredgecolor": "markeredgecolor",
}


def _is_fmt(s):
    if not isinstance(s, str) or len(s) > 4 or s == "":
        return False
    rest = s
    for tok in ("--", "-.", ":", "-"):
        rest = rest.replace(tok, "", 1) if tok in rest else rest
    return all(ch in "bgrcmykwo+*.xsd^v<>ph" for ch in rest)


def _fmt_kwargs(fmt):
    kw = {}
    if not fmt:
        return kw
    ls = None
    for tok in ("--", "-.", ":", "-"):
        if tok in fmt:
            ls = tok
            fmt = fmt.replace(tok, "", 1)
            break
    marker = None
    for ch in fmt:
        if ch in MATLAB_COLORS:
            kw["color"] = MATLAB_COLORS[ch]
        elif ch in "o+*.xsd^v<>ph":
            marker = ch
    if marker:
        kw["marker"] = marker
        kw["linestyle"] = ls or "none"
        kw["markersize"] = 6
    elif ls:
        kw["linestyle"] = ls
    return kw


def _color_value(v):
    if isinstance(v, str):
        return MATLAB_COLORS.get(v, v)
    a = vector(v).astype(float)
    return tuple(np.clip(a[:3], 0, 1))


def _props(args):
    kw = {}
    for k in range(0, len(args) - 1, 2):
        name = args[k]
        if not isinstance(name, str):
            break
        key = _LINE_PROPS.get(name.lower())
        if key is None:
            continue
        val = args[k + 1]
        if key == "color" or key.startswith("marker") and key.endswith("color"):
            kw[key] = _color_value(val)
        elif key in ("linewidth", "markersize"):
            kw[key] = float(scalar(val))
        else:
            kw[key] = val
    return kw


def _xy_groups(args):
    """Split plot(x1, y1, fmt1, x2, y2, ..., 'Prop', value) into groups."""
    groups = []
    i = 0
    n = len(args)
    while i < n:
        a = args[i]
        if isinstance(a, str) and not _is_fmt(a):
            break  # property/value pairs start here
        if isinstance(a, TransferFunction):
            raise MatlabError("Use step(G), bode(G) or rlocus(G) to plot a transfer function.")
        x = num_arg(a)
        y = None
        fmt = None
        if i + 1 < n and not isinstance(args[i + 1], str):
            y = num_arg(args[i + 1])
            i += 2
        else:
            i += 1
        if i < n and _is_fmt(args[i]):
            fmt = args[i]
            i += 1
        if y is None:
            if np.iscomplexobj(x):
                x, y = x.real, x.imag
            else:
                y = x
                x = np.arange(1, (y.shape[1] if y.shape[0] == 1 else y.shape[0]) + 1, dtype=float)
        groups.append((x, y, fmt))
    return groups, _props(args[i:])


def _as_columns(x, y):
    x = np.atleast_2d(np.real(np.asarray(x, dtype=complex if np.iscomplexobj(x) else float)))
    y = np.atleast_2d(np.real(np.asarray(y, dtype=complex if np.iscomplexobj(y) else float)))
    if min(x.shape) == 1:
        x = x.ravel()
        if min(y.shape) == 1:
            y = y.ravel()
            if x.size != y.size:
                raise MatlabError("Vectors must be the same length.")
            return [(x, y)]
        if y.shape[0] == x.size:
            return [(x, y[:, k]) for k in range(y.shape[1])]
        if y.shape[1] == x.size:
            return [(x, y[k, :]) for k in range(y.shape[0])]
        raise MatlabError("Vectors must be the same length.")
    if x.shape == y.shape:
        return [(x[:, k], y[:, k]) for k in range(x.shape[1])]
    raise MatlabError("Vectors must be the same length.")


def _plot_generic(ip, args, method="plot"):
    groups, props = _xy_groups(args)
    if not groups:
        raise MatlabError("Not enough input arguments.")
    ax = ip.figures.plot_axes()
    k0 = len(ax.get_lines())
    lines = []
    for x, y, fmt in groups:
        for xx, yy in _as_columns(x, y):
            kw = {"linewidth": 1.6, "color": PALETTE[(k0 + len(lines)) % len(PALETTE)]}
            kw.update(_fmt_kwargs(fmt))
            kw.update(props)
            kw.setdefault("label", "_nolegend_")
            fn = getattr(ax, method)
            lines.extend(fn(xx, yy, **kw))
    if method in ("semilogx", "loglog") and ax._hl_grid:
        ip.figures.apply_grid(ax, True)
    return lines


@builtin("plot", sig="plot(x, y)  |  plot(x, y, 'r--', 'LineWidth', 2)", en="2-D line plot",
         ar="رسم خطي ثنائي الأبعاد", cat=CAT)
def _plot(ip, args, nargout):
    _plot_generic(ip, args, "plot")


@builtin("semilogx", sig="semilogx(x, y)", en="Plot with logarithmic x-axis", ar="رسم بمحور سيني لوغاريتمي", cat=CAT)
def _semilogx(ip, args, nargout):
    _plot_generic(ip, args, "semilogx")


@builtin("semilogy", sig="semilogy(x, y)", en="Plot with logarithmic y-axis", ar="رسم بمحور صادي لوغاريتمي", cat=CAT)
def _semilogy(ip, args, nargout):
    _plot_generic(ip, args, "semilogy")


@builtin("loglog", sig="loglog(x, y)", en="Log-log plot", ar="رسم لوغاريتمي للمحورين", cat=CAT)
def _loglog(ip, args, nargout):
    _plot_generic(ip, args, "loglog")


@builtin("stem", sig="stem(x, y)", en="Discrete sequence (stem) plot", ar="رسم الإشارات المتقطعة", cat=CAT)
def _stem(ip, args, nargout):
    groups, props = _xy_groups(args)
    ax = ip.figures.plot_axes()
    for k, (x, y, fmt) in enumerate(groups):
        for xx, yy in _as_columns(x, y):
            color = _fmt_kwargs(fmt).get("color", PALETTE[k % len(PALETTE)])
            m, s, b = ax.stem(xx, yy, basefmt=" ")
            m.set_color(color)
            s.set_color(color)
    ax.axhline(0, color="#7A8BA3", linewidth=0.8)


@builtin("stairs", sig="stairs(x, y)", en="Stairstep plot", ar="رسم بياني درجي", cat=CAT)
def _stairs(ip, args, nargout):
    groups, props = _xy_groups(args)
    ax = ip.figures.plot_axes()
    for k, (x, y, fmt) in enumerate(groups):
        for xx, yy in _as_columns(x, y):
            kw = {"color": PALETTE[k % len(PALETTE)], "linewidth": 1.6}
            kw.update(_fmt_kwargs(fmt))
            kw.update(props)
            ax.step(xx, yy, where="post", **kw)


@builtin("bar", sig="bar(y)  |  bar(x, y)", en="Bar graph", ar="رسم بياني بالأعمدة", cat=CAT)
def _bar(ip, args, nargout):
    ax = ip.figures.plot_axes()
    if len(args) == 1:
        y = vector(args[0]).real
        x = np.arange(1, y.size + 1)
    else:
        x, y = vector(args[0]).real, vector(args[1]).real
    ax.bar(x, y, color=PALETTE[0], edgecolor="white", width=0.8)


@builtin("scatter", sig="scatter(x, y)", en="Scatter plot", ar="رسم بياني نقطي", cat=CAT)
def _scatter(ip, args, nargout):
    ax = ip.figures.plot_axes()
    x, y = vector(args[0]).real, vector(args[1]).real
    k = len(ax.collections)
    ax.scatter(x, y, color=PALETTE[k % len(PALETTE)], s=28, zorder=3)


@builtin("area", sig="area(x, y)", en="Filled area plot", ar="رسم مساحة مظللة", cat=CAT)
def _area(ip, args, nargout):
    ax = ip.figures.plot_axes()
    if len(args) == 1:
        y = vector(args[0]).real
        x = np.arange(1, y.size + 1)
    else:
        x, y = vector(args[0]).real, vector(args[1]).real
    ax.fill_between(x, y, color=PALETTE[0], alpha=0.35)
    ax.plot(x, y, color=PALETTE[0], linewidth=1.4)


@builtin("fplot", sig="fplot(@(x) f, [a b])", en="Plot a function over an interval", ar="رسم دالة على فترة", cat=CAT)
def _fplot(ip, args, nargout):
    h = args[0]
    if not isinstance(h, FunctionHandle):
        raise MatlabError("fplot expects a function handle, e.g. fplot(@(x) sin(x), [0 10])")
    lim = vector(args[1]).real if len(args) > 1 and not isinstance(args[1], str) else np.array([-5.0, 5.0])
    x = np.linspace(lim[0], lim[1], 600)
    try:
        y = vector(ip.call_value(h, x.reshape(1, -1))).real
        if y.size != x.size:
            raise ValueError
    except Exception:
        y = np.array([float(np.real(scalar(ip.call_value(h, np.array([[xi]]))))) for xi in x])
    fmt = args[2] if len(args) > 2 and isinstance(args[2], str) else None
    _plot_generic(ip, [x.reshape(1, -1), y.reshape(1, -1)] + ([fmt] if fmt else []))


@builtin("figure", sig="figure  |  figure(n)", en="Create a new figure window (or select figure n)",
         ar="إنشاء نافذة رسم جديدة", cat=CAT)
def _figure(ip, args, nargout):
    num = None
    if args and not isinstance(args[0], str):
        num = int_arg(args[0], "Figure number")
        if num < 1:
            raise MatlabError("Figure number must be a positive integer, e.g. figure(2).")
    ip.figures.new_figure(num)
    ip.figures.touch()


@builtin("hold", sig="hold on  |  hold off", en="Keep existing plots when adding new ones",
         ar="الإبقاء على الرسم السابق عند إضافة رسم جديد", cat=CAT)
def _hold(ip, args, nargout):
    fm = ip.figures
    fig = fm.gcf()
    ax = fm.gca()
    on = (not ax._hl_hold) if not args else args[0].lower() in ("on", "all")
    fig._hl_hold = on
    for a in fig.axes:
        a._hl_hold = on


@builtin("grid", sig="grid on  |  grid off  |  grid minor", en="Show or hide grid lines",
         ar="إظهار أو إخفاء خطوط الشبكة", cat=CAT)
def _grid(ip, args, nargout):
    fm = ip.figures
    ax = fm.gca()
    on = (not ax._hl_grid) if not args else args[0].lower() in ("on", "minor")
    fig = fm.gcf()
    targets = fig.axes if getattr(fig, "_hl_bode", None) else [ax]
    for a in targets:
        fm.apply_grid(a, on)
        if args and args[0].lower() == "minor":
            a.minorticks_on()
            a.grid(True, which="minor", color="#EEF3F9", linewidth=0.5)


@builtin("title", sig="title('text')", en="Plot title", ar="عنوان الرسم", cat=CAT)
def _title(ip, args, nargout):
    ax = ip.figures.gca()
    ax.set_title(_text(args[0]), fontsize=11, fontweight="bold")
    ip.figures.touch()


@builtin("xlabel", sig="xlabel('text')", en="X-axis label", ar="تسمية المحور السيني", cat=CAT)
def _xlabel(ip, args, nargout):
    ax = ip.figures.gca()
    fig = ip.figures.gcf()
    bode = getattr(fig, "_hl_bode", None)
    (bode[1] if bode and ax is bode[0] else ax).set_xlabel(_text(args[0]))
    ip.figures.touch()


@builtin("ylabel", sig="ylabel('text')", en="Y-axis label", ar="تسمية المحور الصادي", cat=CAT)
def _ylabel(ip, args, nargout):
    ip.figures.gca().set_ylabel(_text(args[0]))
    ip.figures.touch()


_GREEK = ("alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|lambda|mu|nu|xi|pi|rho|"
          "sigma|tau|upsilon|phi|chi|psi|omega|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Phi|Psi|Omega|"
          "infty|circ|pm|times|leq|geq|neq|approx|rightarrow|leftarrow")
_TEX_RE = re.compile(r"\\(" + _GREEK + r")(?![A-Za-z])|([_^])\{([^}]*)\}|([_^])(\w)")


def tex(s):
    """MATLAB TeX interpreter subset: Greek letters and x^{2}, x_{1} -> mathtext."""
    if "\\" not in s and "^" not in s and "_" not in s:
        return s

    def sub(m):
        if m.group(1):
            return f"$\\{m.group(1)}$"
        if m.group(2):
            return f"$\\mathregular{{{m.group(2)}{{{m.group(3)}}}}}$"
        return f"$\\mathregular{{{m.group(4)}{{{m.group(5)}}}}}$"
    out = _TEX_RE.sub(sub, s)
    return out.replace("$$", "")


def _text(v):
    if isinstance(v, Cell):
        return "\n".join(_text(x) for x in v.items)
    if isinstance(v, str):
        return tex(v)
    from .core import num2str_value
    return num2str_value(v)


@builtin("text", sig="text(x, y, 'str')", en="Add text to the plot", ar="إضافة نص إلى الرسم", cat=CAT)
def _textfn(ip, args, nargout):
    ax = ip.figures.gca()
    ax.text(float(scalar(args[0])), float(scalar(args[1])), _text(args[2]), fontsize=9, color="#24324A")
    ip.figures.touch()


@builtin("gtext", sig="gtext('text')", en="Place text on the plot (drag it with the mouse to position it)",
         ar="إضافة نص إلى الرسم يمكن سحبه بالفأرة", cat=CAT)
def _gtext(ip, args, nargout):
    ax = ip.figures.gca()
    n = getattr(ax, "_hl_gtext_count", 0)
    ax._hl_gtext_count = n + 1
    # MATLAB waits for a mouse click; here the label is placed and can be dragged.
    ann = ax.annotate(_text(args[0]), xy=(0.62, 0.9 - 0.08 * (n % 10)), xycoords="axes fraction",
                      fontsize=9, color="#24324A",
                      bbox=dict(boxstyle="round,pad=0.25", fc="#FFFDE7", ec="#FFB300", lw=0.8))
    ann._hl_draggable = True
    ip.figures.touch()


def _axes3d(ip):
    fm = ip.figures
    fig = fm.gcf()
    ax = getattr(fig, "_hl_current_ax", None)
    if ax is not None and ax in fig.axes and getattr(ax, "name", "") == "3d" and ax._hl_hold:
        return ax
    if ax is not None and ax in fig.axes:
        key = getattr(ax, "_hl_key", None)
        fig.delaxes(ax)
    else:
        key = None
    if key:
        ax = fig.add_subplot(*key, projection="3d")
        ax._hl_key = key
    else:
        fig.clf()
        ax = fig.add_subplot(1, 1, 1, projection="3d")
    ax._hl_hold = False
    ax._hl_grid = True
    fig._hl_current_ax = ax
    fig._hl_bode = None
    fm.touch()
    return ax


def _surface_args(args):
    nums = [num_arg(a).astype(float) for a in args if not isinstance(a, str)]
    if len(nums) == 1:
        Z = nums[0]
        X, Y = np.meshgrid(np.arange(1, Z.shape[1] + 1), np.arange(1, Z.shape[0] + 1))
    elif len(nums) >= 3:
        X, Y, Z = nums[:3]
        if min(X.shape) == 1 and min(Y.shape) == 1:
            X, Y = np.meshgrid(X.ravel(), Y.ravel())
    else:
        raise MatlabError("Usage: mesh(Z) or mesh(X, Y, Z)")
    return X, Y, Z


@builtin("mesh", sig="mesh(Z)  |  mesh(X, Y, Z)", en="3-D mesh (wireframe) surface", ar="سطح شبكي ثلاثي الأبعاد", cat=CAT)
def _mesh(ip, args, nargout):
    X, Y, Z = _surface_args(args)
    ax = _axes3d(ip)
    ax.plot_wireframe(X, Y, Z, rstride=max(1, Z.shape[0] // 40), cstride=max(1, Z.shape[1] // 40),
                      color="#1E88E5", linewidth=0.6)


@builtin("surf", sig="surf(Z)  |  surf(X, Y, Z)", en="3-D colored surface", ar="سطح ملون ثلاثي الأبعاد", cat=CAT)
def _surf(ip, args, nargout):
    X, Y, Z = _surface_args(args)
    ax = _axes3d(ip)
    ax.plot_surface(X, Y, Z, cmap="turbo", rstride=max(1, Z.shape[0] // 60),
                    cstride=max(1, Z.shape[1] // 60), linewidth=0.2, edgecolor="#FFFFFF40")


@builtin("view", sig="view(az, el)", en="3-D view angle (azimuth, elevation in degrees)", ar="زاوية الرؤية الثلاثية", cat=CAT)
def _view(ip, args, nargout):
    ax = ip.figures.gca()
    if getattr(ax, "name", "") != "3d":
        return
    if len(args) == 1:
        v = vector(args[0]).real
        az, el = (v[0], v[1]) if v.size >= 2 else ((0, 90) if v[0] == 2 else (-37.5, 30))
    else:
        az, el = float(scalar(args[0])), float(scalar(args[1]))
    ax.view_init(elev=el, azim=az - 90)
    ip.figures.touch()


@builtin("zlabel", sig="zlabel('text')", en="Z-axis label", ar="تسمية المحور z", cat=CAT)
def _zlabel(ip, args, nargout):
    ax = ip.figures.gca()
    if getattr(ax, "name", "") == "3d":
        ax.set_zlabel(_text(args[0]))
    ip.figures.touch()


@builtin("polar", sig="polar(theta, rho)", en="Plot in polar coordinates", ar="رسم بالإحداثيات القطبية", cat=CAT)
def _polar(ip, args, nargout):
    fm = ip.figures
    fig = fm.gcf()
    old = getattr(fig, "_hl_current_ax", None)
    if old is not None and old in fig.axes and getattr(old, "name", "") == "polar" and old._hl_hold:
        ax = old
    else:
        fig.clf()
        ax = fig.add_subplot(1, 1, 1, projection="polar")
        ax._hl_hold = False
        ax._hl_grid = True
        fig._hl_current_ax = ax
        fig._hl_bode = None
    if len(args) < 2:
        raise MatlabError("Usage: polar(theta, rho)")
    th = vector(args[0]).real
    rho = vector(args[1]).real
    if th.size != rho.size:
        raise MatlabError("theta and rho must have the same length.")
    kw = {"linewidth": 1.6, "color": PALETTE[len(ax.get_lines()) % len(PALETTE)]}
    if len(args) > 2 and isinstance(args[2], str):
        kw.update(_fmt_kwargs(args[2]))
    ax.plot(th, rho, **kw)
    fm.touch()


@builtin("legend", sig="legend('a', 'b', ...)  |  legend off", en="Add a legend", ar="إضافة مفتاح الرسم", cat=CAT)
def _legend(ip, args, nargout):
    ax = ip.figures.gca()
    if args and isinstance(args[0], str) and args[0].lower() in ("off", "hide"):
        if ax.get_legend():
            ax.get_legend().remove()
        ip.figures.touch()
        return
    labels = []
    loc = "best"
    i = 0
    while i < len(args):
        a = args[i]
        if isinstance(a, str) and a.lower() == "location" and i + 1 < len(args):
            loc = {"northeast": "upper right", "northwest": "upper left", "southeast": "lower right",
                   "southwest": "lower left", "best": "best", "north": "upper center",
                   "south": "lower center", "east": "center right", "west": "center left"}.get(
                str(args[i + 1]).lower(), "best")
            i += 2
            continue
        if isinstance(a, Cell):
            labels.extend(_text(x) for x in a.items)
        elif isinstance(a, str) and a.lower() not in ("show", "on"):
            labels.append(tex(a))
        i += 1
    lines = [l for l in ax.get_lines()
             if not (l.get_linestyle() == ":" and l.get_linewidth() < 1.0)]
    if labels:
        for l, lab in zip(lines, labels):
            l.set_label(lab)
        ax.legend(lines[:len(labels)], labels, fontsize=8, framealpha=0.9, loc=loc)
    else:
        ax.legend(fontsize=8, framealpha=0.9, loc=loc)
    ip.figures.touch()


@builtin("subplot", sig="subplot(m, n, p)", en="Create axes in a tiled layout", ar="تقسيم نافذة الرسم", cat=CAT)
def _subplot(ip, args, nargout):
    if len(args) == 1:
        code = int_arg(args[0])
        m, n, p = code // 100, (code // 10) % 10, code % 10
    else:
        m, n, p = (int_arg(a) for a in args[:3])
    if p < 1 or p > m * n:
        raise MatlabError("Index exceeds number of subplots.")
    fig = ip.figures.gcf()
    if getattr(fig, "_hl_bode", None):
        ip.figures.clear_figure(fig)
        fig._hl_bode = None
    ip.figures.subplot(m, n, p)


@builtin("axis", sig="axis([xmin xmax ymin ymax])  |  axis equal  |  axis tight",
         en="Set axis limits and scaling", ar="تحديد حدود المحاور", cat=CAT)
def _axis(ip, args, nargout):
    ax = ip.figures.gca()
    if not args:
        return np.array([list(ax.get_xlim()) + list(ax.get_ylim())])
    a = args[0]
    if isinstance(a, str):
        mode = a.lower()
        if mode == "equal":
            ax.set_aspect("equal", adjustable="datalim")
        elif mode == "tight":
            ax.autoscale(enable=True, tight=True)
        elif mode in ("auto", "normal"):
            ax.set_aspect("auto")
            ax.autoscale(True)
        elif mode == "square":
            ax.set_box_aspect(1)
        elif mode == "off":
            ax.set_axis_off()
        elif mode == "on":
            ax.set_axis_on()
    else:
        lim = vector(a).real
        ax.set_xlim(lim[0], lim[1])
        if lim.size >= 4:
            ax.set_ylim(lim[2], lim[3])
    ip.figures.touch()


@builtin("xlim", sig="xlim([xmin xmax])", en="Set x-axis limits", ar="حدود المحور السيني", cat=CAT)
def _xlim(ip, args, nargout):
    ax = ip.figures.gca()
    if not args:
        return np.array([list(ax.get_xlim())])
    lim = vector(args[0]).real
    fig = ip.figures.gcf()
    for a in (fig._hl_bode if getattr(fig, "_hl_bode", None) else [ax]):
        a.set_xlim(lim[0], lim[1])
    ip.figures.touch()


@builtin("ylim", sig="ylim([ymin ymax])", en="Set y-axis limits", ar="حدود المحور الصادي", cat=CAT)
def _ylim(ip, args, nargout):
    ax = ip.figures.gca()
    if not args:
        return np.array([list(ax.get_ylim())])
    lim = vector(args[0]).real
    ax.set_ylim(lim[0], lim[1])
    ip.figures.touch()


@builtin("close", sig="close  |  close all  |  close(n)", en="Close figure windows", ar="إغلاق نوافذ الرسم", cat=CAT)
def _close(ip, args, nargout):
    if args and isinstance(args[0], str):
        ip.figures.close("all" if args[0].lower() == "all" else None)
    elif args:
        ip.figures.close(int_arg(args[0]))
    else:
        ip.figures.close()


@builtin("clf", sig="clf", en="Clear the current figure", ar="مسح الرسم الحالي", cat=CAT)
def _clf(ip, args, nargout):
    fig = ip.figures.gcf()
    ip.figures.clear_figure(fig)
    fig._hl_bode = None
