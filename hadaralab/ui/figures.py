"""Figure panel: one tab per figure, with toolbar, data tips and export."""

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QPushButton,
                               QTabWidget, QVBoxLayout, QWidget)

from .theme import C, set_css, qc, themed, themed_color
from ..graphics import apply_theme


class Toolbar(NavigationToolbar2QT):
    def _icon(self, name):
        # Pick the icon color from our theme: the transparent toolbar background
        # would otherwise confuse matplotlib's own dark-mode detection.
        from matplotlib import cbook
        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtGui import QIcon, QPixmap
        from .theme import is_dark
        path = cbook._get_data_path("images", name)
        large = path.with_name(path.name.replace(".png", "_large.png"))
        pm = QPixmap(str(large if large.exists() else path))
        pm.setDevicePixelRatio(self.devicePixelRatioF() or 1)
        if is_dark():
            mask = pm.createMaskFromColor(qc(0, 0, 0), _Qt.MaskMode.MaskOutColor)
            pm.fill(qc(180, 184, 191))
            pm.setMask(mask)
        return QIcon(pm)


class FigureView(QWidget):
    def __init__(self, fig, parent=None):
        super().__init__(parent)
        self.fig = fig
        self.canvas = FigureCanvasQTAgg(fig)
        self.canvas.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.toolbar = Toolbar(self.canvas, self)
        set_css(self.toolbar, "QToolBar { background: transparent; border: none; spacing: 2px; }"
                                   "QToolButton { border-radius: 6px; padding: 3px; }"
                                   f"QToolButton:hover {{ background: {C['select']}; }}"
                                   f"QToolButton:checked {{ background: {C['select']}; }}"
                                   "QLabel { color: #6B7C93; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        top = QHBoxLayout()
        top.addWidget(self.toolbar, 1)
        save = QPushButton("Save PNG")
        save.setProperty("class", "Secondary")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self.save_png)
        top.addWidget(save)
        lay.addLayout(top)
        lay.addWidget(self.canvas, 1)
        self.hint = QLabel("Tip: click a curve to see its values (data tip). On a root locus the "
                           "gain K, damping ζ and ωn are shown. Right-click clears.")
        set_css(self.hint, "color: #8A9AB0; font-size: 8pt; padding: 0 4px;")
        lay.addWidget(self.hint)
        self.tips = []
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.enable_dragging()

    def enable_dragging(self):
        """gtext() labels can be moved with the mouse."""
        for ax in self.fig.axes:
            for t in ax.texts:
                if getattr(t, "_hl_draggable", False) and not getattr(t, "_hl_drag", None):
                    t._hl_drag = t.draggable(True)

    def save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save figure", f"{self.fig._hl_title}.png",
                                              "PNG image (*.png);;SVG (*.svg);;PDF (*.pdf)")
        if path:
            self.fig.savefig(path, dpi=200)

    def clear_tips(self):
        for t in self.tips:
            try:
                t.remove()
            except (ValueError, NotImplementedError):
                pass
        self.tips = []

    def on_click(self, event):
        if self.toolbar.mode:
            return
        if event.button == 3:
            self.clear_tips()
            self.canvas.draw_idle()
            return
        ax = event.inaxes
        if ax is None or event.xdata is None:
            return
        if hasattr(ax, "_hl_rlocus"):
            self._rlocus_tip(ax, event)
            return
        best = None
        for line in ax.get_lines():
            xd, yd = line.get_xdata(), line.get_ydata()
            if len(xd) < 2 or line.get_label().startswith("_child"):
                continue
            pts = ax.transData.transform(np.column_stack([np.asarray(xd, float), np.asarray(yd, float)]))
            d = np.hypot(pts[:, 0] - event.x, pts[:, 1] - event.y)
            i = int(np.nanargmin(d))
            if best is None or d[i] < best[0]:
                best = (d[i], xd[i], yd[i], line)
        if best is None or best[0] > 25:
            return
        _, x, y, line = best
        self._place_tip(ax, x, y, f"X: {x:.4g}\nY: {y:.4g}", line.get_color())

    def _rlocus_tip(self, ax, event):
        G, gains, roots = ax._hl_rlocus
        pts = roots.ravel()
        ks = np.repeat(gains, roots.shape[1])
        ok = np.isfinite(pts)
        pts, ks = pts[ok], ks[ok]
        xy = ax.transData.transform(np.column_stack([pts.real, pts.imag]))
        d = np.hypot(xy[:, 0] - event.x, xy[:, 1] - event.y)
        i = int(np.argmin(d))
        if d[i] > 30:
            return
        s, k = pts[i], ks[i]
        wn = abs(s)
        zeta = -s.real / wn if wn > 0 else 1.0
        os_ = 100 * np.exp(-zeta * np.pi / np.sqrt(1 - zeta ** 2)) if 0 < zeta < 1 else 0.0
        text = (f"Gain K: {k:.4g}\nPole: {s.real:.4g} {'+' if s.imag >= 0 else '-'} {abs(s.imag):.4g}j\n"
                f"Damping ζ: {zeta:.4g}\nOvershoot: {os_:.3g} %\nFrequency ωn: {wn:.4g} rad/s")
        self._place_tip(ax, s.real, s.imag, text, "#E91E63")

    def _place_tip(self, ax, x, y, text, color):
        self.clear_tips()
        dot, = ax.plot([x], [y], marker="o", markersize=8, markerfacecolor=themed_color("white"),
                       markeredgecolor=color, markeredgewidth=2, zorder=10, label="_tip")
        xl = ax.get_xlim()
        right = (x - xl[0]) / (xl[1] - xl[0] or 1) > 0.6 if ax.get_xscale() == "linear" else \
            (np.log10(max(x, 1e-300)) - np.log10(xl[0])) / (np.log10(xl[1]) - np.log10(xl[0])) > 0.6
        ann = ax.annotate(text, xy=(x, y), xytext=(-14 if right else 14, 14),
                          textcoords="offset points", ha="right" if right else "left",
                          fontsize=8.5, color=themed_color("#24324A"), zorder=11,
                          bbox=dict(boxstyle="round,pad=0.45", fc=themed_color("white"), ec=color, lw=1.4, alpha=0.96),
                          arrowprops=dict(arrowstyle="-", color=color, lw=1.2))
        self.tips = [dot, ann]
        self.canvas.draw_idle()


class FigurePanel(QTabWidget):
    figure_closed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.views = {}
        self.tabCloseRequested.connect(self._close_tab)
        self.empty = QLabel("Figures will appear here.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_css(self.empty, "color: #8A9AB0; font-size: 11pt;")
        self.addTab(self.empty, "Figures")
        self.tabBar().setTabButton(0, self.tabBar().ButtonPosition.RightSide, None)

    def sync(self, manager, changed=()):
        """Match the tabs with the FigureManager after a run."""
        for num in list(self.views):
            if num not in manager.figures or manager.figures[num] is not self.views[num].fig:
                self._remove(num)
        for num, fig in sorted(manager.figures.items()):
            if num not in self.views:
                apply_theme(fig)
                view = FigureView(fig)
                self.views[num] = view
                self.addTab(view, f"Figure {num}")
            elif num in changed:
                self.views[num].clear_tips()
                self.views[num].enable_dragging()
        if self.views and self.indexOf(self.empty) != -1:
            self.removeTab(self.indexOf(self.empty))
        if not self.views and self.indexOf(self.empty) == -1:
            self.addTab(self.empty, "Figures")
        for num in changed:
            if num in self.views:
                apply_theme(self.views[num].fig)
                self.views[num].canvas.draw_idle()
        if manager.current in self.views:
            self.setCurrentWidget(self.views[manager.current])

    def _remove(self, num):
        view = self.views.pop(num)
        idx = self.indexOf(view)
        if idx != -1:
            self.removeTab(idx)
        view.deleteLater()

    def _close_tab(self, idx):
        w = self.widget(idx)
        for num, view in list(self.views.items()):
            if view is w:
                self._remove(num)
                self.figure_closed.emit(num)
                break
        if not self.views and self.indexOf(self.empty) == -1:
            self.addTab(self.empty, "Figures")
