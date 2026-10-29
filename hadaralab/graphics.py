"""Figure management for plot commands.

Plot builtins draw on matplotlib Figure objects owned by FigureManager.
The GUI wraps each Figure in a Qt canvas; tests can render them with Agg.
"""

from matplotlib.figure import Figure

# Bright, high-contrast palette (light theme)
PALETTE = ["#1E88E5", "#FF6D00", "#00BFA5", "#E91E63", "#7C4DFF",
           "#FFB300", "#43A047", "#00ACC1", "#F4511E", "#8E24AA"]

AX_STYLE = {
    "facecolor": "#FFFFFF",
    "grid": "#E3EBF5",
    "spine": "#B8C7D9",
    "text": "#24324A",
}

# MATLAB single-letter colors mapped to the bright palette
MATLAB_COLORS = {
    "b": "#1E88E5", "r": "#E53935", "g": "#43A047", "c": "#00ACC1",
    "m": "#D81B60", "y": "#FDD835", "k": "#212121", "w": "#FFFFFF",
}


def _dark_color(c):
    """Map one matplotlib color to the dark theme (keeps alpha)."""
    from matplotlib import colors as mcolors
    from .ui.theme import DARK_MAP, DARK_UI, LIGHT_MAP
    if c is None or (isinstance(c, str) and c.lower() == "none"):
        return c
    try:
        r, g, b, a = mcolors.to_rgba(c)
    except ValueError:
        return c
    if a == 0:
        return c
    hx = mcolors.to_hex((r, g, b)).upper()
    if hx in DARK_MAP:
        return mcolors.to_rgba(DARK_MAP[hx], a)
    if hx in LIGHT_MAP:          # already a dark-theme color
        return c
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lum > 0.92:               # near white surfaces
        return mcolors.to_rgba(DARK_UI["surface"], a)
    if lum < 0.22:               # near black text and lines
        return mcolors.to_rgba(DARK_UI["text"], a)
    return c


def apply_theme(fig):
    """Recolor a finished figure for the current theme (no-op in light mode)."""
    from matplotlib.collections import Collection
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.text import Annotation, Text
    from .ui.theme import DARK_UI, is_dark
    if not is_dark():
        return
    for art in fig.findobj():
        try:
            if isinstance(art, Line2D):
                art.set_color(_dark_color(art.get_color()))
                art.set_markerfacecolor(_dark_color(art.get_markerfacecolor()))
                art.set_markeredgecolor(_dark_color(art.get_markeredgecolor()))
            elif isinstance(art, Text):
                art.set_color(_dark_color(art.get_color()))
                box = art.get_bbox_patch()
                if box is not None:
                    box.set_facecolor(_dark_color(box.get_facecolor()))
                    box.set_edgecolor(_dark_color(box.get_edgecolor()))
                if isinstance(art, Annotation) and art.arrow_patch is not None:
                    art.arrow_patch.set_color(_dark_color(art.arrow_patch.get_edgecolor()))
            elif isinstance(art, Patch):
                art.set_facecolor(_dark_color(art.get_facecolor()))
                art.set_edgecolor(_dark_color(art.get_edgecolor()))
            elif isinstance(art, Collection):
                fc, ec = art.get_facecolors(), art.get_edgecolors()
                if len(fc):
                    art.set_facecolors([_dark_color(tuple(c)) for c in fc])
                if len(ec):
                    art.set_edgecolors([_dark_color(tuple(c)) for c in ec])
        except (ValueError, TypeError, AttributeError):
            continue
    for ax in fig.axes:
        ax.tick_params(colors=DARK_UI["text2"], labelcolor=DARK_UI["text2"])
        if getattr(ax, "name", "") == "3d":
            for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
                axis.set_pane_color(DARK_UI["surface"])
                axis._axinfo["grid"]["color"] = DARK_UI["grid"]


def style_axes(ax):
    from cycler import cycler
    ax.set_facecolor(AX_STYLE["facecolor"])
    ax.set_prop_cycle(cycler(color=PALETTE))
    for side, sp in ax.spines.items():
        sp.set_color(AX_STYLE["spine"])
        sp.set_linewidth(0.9)
    ax.tick_params(colors=AX_STYLE["text"], labelsize=9)
    ax.xaxis.label.set_color(AX_STYLE["text"])
    ax.yaxis.label.set_color(AX_STYLE["text"])
    ax.title.set_color(AX_STYLE["text"])
    if not hasattr(ax, "_hl_hold"):
        ax._hl_hold = False
    if not hasattr(ax, "_hl_grid"):
        ax._hl_grid = False


class FigureManager:
    def __init__(self):
        self.figures = {}        # number -> Figure
        self.current = None      # current figure number
        self.listeners = []      # callbacks(event, number)
        self.dirty = set()

    def notify(self, event, num):
        for cb in self.listeners:
            cb(event, num)

    def new_figure(self, num=None):
        if num is None:
            num = 1
            while num in self.figures:
                num += 1
        if num not in self.figures:
            fig = Figure(figsize=(6.4, 4.8), dpi=100, facecolor="#FFFFFF", layout="constrained")
            fig._hl_number = num
            fig._hl_title = f"Figure {num}"
            self.figures[num] = fig
            self.current = num
            self.notify("created", num)
        else:
            self.current = num
            self.notify("raised", num)
        return self.figures[num]

    def gcf(self):
        if self.current is None or self.current not in self.figures:
            return self.new_figure()
        return self.figures[self.current]

    def gca(self):
        fig = self.gcf()
        ax = getattr(fig, "_hl_current_ax", None)
        if ax is None or ax not in fig.axes:
            ax = fig.add_subplot(1, 1, 1)
            style_axes(ax)
            fig._hl_current_ax = ax
        return ax

    def plot_axes(self):
        """Axes for a new plot: cleared unless `hold on` is active."""
        ax = self.gca()
        if not ax._hl_hold:
            grid = ax._hl_grid
            ax.cla()
            for attr in ("_hl_rlocus", "_hl_kind"):
                if hasattr(ax, attr):
                    delattr(ax, attr)
            style_axes(ax)
            ax._hl_hold = False
            ax._hl_grid = grid
            if grid:
                self.apply_grid(ax, True)
        self.touch()
        return ax

    def subplot(self, m, n, p):
        fig = self.gcf()
        key = (m, n, p)
        for ax in fig.axes:
            if getattr(ax, "_hl_key", None) == key:
                fig._hl_current_ax = ax
                return ax
        # remove axes that overlap a new grid layout (like MATLAB)
        for ax in list(fig.axes):
            k = getattr(ax, "_hl_key", None)
            if k is None or k[:2] != (m, n):
                fig.delaxes(ax)
        ax = fig.add_subplot(m, n, p)
        ax._hl_key = key
        style_axes(ax)
        fig._hl_current_ax = ax
        self.touch()
        return ax

    def clear_figure(self, fig=None):
        fig = fig or self.gcf()
        fig.clf()
        fig._hl_current_ax = None
        self.touch()

    def close(self, which=None):
        if which == "all":
            for num in list(self.figures):
                del self.figures[num]
                self.notify("closed", num)
            self.current = None
            return
        num = self.current if which is None else which
        if num in self.figures:
            del self.figures[num]
            self.notify("closed", num)
            self.current = max(self.figures) if self.figures else None

    def apply_grid(self, ax, on):
        ax._hl_grid = on
        if on:
            ax.grid(True, which="major", color=AX_STYLE["grid"], linewidth=0.9)
            if ax.get_xscale() == "log":
                ax.grid(True, which="minor", color=AX_STYLE["grid"], linewidth=0.5, alpha=0.7)
        else:
            ax.grid(False, which="both")
        self.touch()

    def touch(self):
        if self.current is not None:
            self.dirty.add(self.current)

    def finalize(self):
        """Called after a run: report figures that changed (layout is automatic)."""
        changed = sorted(self.dirty)
        self.dirty.clear()
        return changed
