"""Interactive tools: PID Tuner, Routh-Hurwitz analyzer, Block-Diagram builder."""

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QPushButton,
                               QSizePolicy, QSlider, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .theme import C, is_dark, set_css, qc, themed
from ..control import analysis as an
from ..control.tf import TransferFunction, feedback, pid, poly_to_str
from ..graphics import PALETTE, apply_theme, style_axes


def parse_poly(text):
    text = text.strip().strip("[]").replace(",", " ")
    if not text:
        raise ValueError("empty polynomial")
    p = np.array([float(x) for x in text.split()])
    if not np.all(np.isfinite(p)):
        raise ValueError("coefficients must be finite numbers")
    return p


def tf_label(G):
    return f"({poly_to_str(G.num)}) / ({poly_to_str(G.den)})"


def make_canvas(height=4.0):
    fig = Figure(figsize=(6, height), dpi=100, facecolor="white", layout="constrained")
    canvas = FigureCanvasQTAgg(fig)
    canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return fig, canvas


def metric_card(title, color):
    frame = QFrame()
    set_css(frame, f"QFrame {{ background: white; border: 1px solid {C['border']};"
                        f" border-left: 4px solid {color}; border-radius: 10px; }}")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(10, 6, 10, 6)
    lay.setSpacing(0)
    t = QLabel(title)
    set_css(t, "border: none; color: #6B7C93; font-size: 8.5pt;")
    v = QLabel("—")
    set_css(v, f"border: none; color: {color}; font-size: 14pt; font-weight: 700;")
    lay.addWidget(t)
    lay.addWidget(v)
    frame.value = v
    return frame


def banner():
    lab = QLabel()
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lab.setWordWrap(True)
    lab.setMinimumHeight(40)
    return lab


def set_banner(lab, kind, text):
    colors = {"ok": ("#E8F8F0", "#2E7D32", "#A5D6A7"),
              "bad": ("#FDECEF", "#C62828", "#F48FB1"),
              "warn": ("#FFF6E5", "#E65100", "#FFCC80")}
    bg, fg, br = colors[kind]
    set_css(lab, f"background: {bg}; color: {fg}; border: 1px solid {br}; border-radius: 10px;"
                      f" font-weight: 700; font-size: 10.5pt; padding: 6px;")
    lab.setText(text)


class ToolDialog(QDialog):
    send_code = Signal(str)

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(1180, 720)


# ---------------------------------------------------------------------------
# PID Tuner
# ---------------------------------------------------------------------------

class GainControl(QWidget):
    changed = Signal()

    def __init__(self, name, color, vmax, value=0.0):
        super().__init__()
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lab = QLabel(name)
        set_css(lab, f"font-weight: 700; color: {color}; font-size: 11pt;")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(3)
        self.spin.setRange(0, 1e6)
        self.spin.setSingleStep(0.1)
        self.spin.setMinimumWidth(95)
        self.maxspin = QDoubleSpinBox()
        self.maxspin.setRange(0.01, 1e6)
        self.maxspin.setValue(vmax)
        self.maxspin.setPrefix("max ")
        self.maxspin.setDecimals(1)
        self.maxspin.setMaximumWidth(110)
        lay.addWidget(lab, 0, 0)
        lay.addWidget(self.slider, 0, 1)
        lay.addWidget(self.spin, 0, 2)
        lay.addWidget(self.maxspin, 0, 3)
        lay.setColumnStretch(1, 1)
        self._lock = False
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)
        self.maxspin.valueChanged.connect(lambda _: self._from_spin(self.spin.value()))
        self.set_value(value)

    def _from_slider(self, v):
        if self._lock:
            return
        self._lock = True
        self.spin.setValue(v / 1000 * self.maxspin.value())
        self._lock = False
        self.changed.emit()

    def _from_spin(self, v):
        if self._lock:
            return
        self._lock = True
        if v > self.maxspin.value():
            self.maxspin.setValue(v)
        self.slider.setValue(int(round(v / self.maxspin.value() * 1000)))
        self._lock = False
        self.changed.emit()

    def set_value(self, v):
        self.spin.setValue(v)
        self._from_spin(v)

    def value(self):
        return self.spin.value()

    def set_enabled(self, on):
        self.setEnabled(on)


class PIDTuner(ToolDialog):
    def __init__(self, workspace=None, parent=None):
        super().__init__("PID Tuner  —  ضبط متحكم PID", parent)
        self.workspace = workspace or {}
        root = QHBoxLayout(self)
        root.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(10)
        gb = QGroupBox("Plant  G(s)  —  النظام المراد التحكم به")
        g = QGridLayout(gb)
        self.num = QLineEdit("1")
        self.den = QLineEdit("1 10 20")
        g.addWidget(QLabel("num:"), 0, 0)
        g.addWidget(self.num, 0, 1)
        g.addWidget(QLabel("den:"), 1, 0)
        g.addWidget(self.den, 1, 1)
        self.ws_combo = QComboBox()
        self.ws_combo.addItem("— from workspace —")
        for name, v in sorted(self.workspace.items()):
            if isinstance(v, TransferFunction):
                self.ws_combo.addItem(name)
        self.ws_combo.currentTextChanged.connect(self._load_ws)
        g.addWidget(self.ws_combo, 2, 0, 1, 2)
        self.plant_lbl = QLabel()
        set_css(self.plant_lbl, "font-family: 'JetBrains Mono', Consolas; color: #1565C0;")
        self.plant_lbl.setWordWrap(True)
        g.addWidget(self.plant_lbl, 3, 0, 1, 2)
        left.addWidget(gb)

        gb2 = QGroupBox("Controller  C(s) = Kp + Ki/s + Kd·s")
        v2 = QVBoxLayout(gb2)
        self.ctype = QComboBox()
        self.ctype.addItems(["PID", "PI", "PD", "P"])
        self.ctype.currentTextChanged.connect(self._type_changed)
        v2.addWidget(self.ctype)
        self.kp = GainControl("Kp", PALETTE[0], 500, 300)
        self.ki = GainControl("Ki", PALETTE[2], 500, 300)
        self.kd = GainControl("Kd", PALETTE[1], 100, 10)
        for gc in (self.kp, self.ki, self.kd):
            v2.addWidget(gc)
            gc.changed.connect(self.schedule)
        row = QHBoxLayout()
        auto = QPushButton("Auto Tune")             # brand blue (default button)
        auto.clicked.connect(self.auto_tune)
        zn = QPushButton("Ziegler-Nichols")
        zn.setProperty("class", "Teal")
        zn.setToolTip("Ogata ch. 10 - second method (critical gain Kcr, period Pcr),\n"
                      "or first method (S-shaped step response) if the loop never becomes unstable.")
        zn.clicked.connect(self.ziegler_nichols)
        row.addWidget(zn)
        reset = QPushButton("Reset")
        reset.setProperty("class", "Secondary")
        reset.clicked.connect(lambda: [self.kp.set_value(1), self.ki.set_value(0), self.kd.set_value(0)])
        row.addWidget(auto)
        row.addWidget(reset)
        v2.addLayout(row)
        left.addWidget(gb2)

        tips = QLabel(themed(
            "<b>أثر كل معامل (Ogata / CTMS):</b><br>"
            "• <span style='color:#1E88E5'><b>Kp</b></span>: يُقلِّل زمن الصعود، ويزيد التجاوز، ويُقلِّل الخطأ.<br>"
            "• <span style='color:#00BFA5'><b>Ki</b></span>: يُلغي الخطأ في الحالة المستقرة، لكنه يزيد التجاوز.<br>"
            "• <span style='color:#FF6D00'><b>Kd</b></span>: يُقلِّل التجاوز وزمن الاستقرار (يزيد التخميد)."))
        tips.setWordWrap(True)
        tips.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        set_css(tips, "background: #F3F8FF; border: 1px solid #DCE6F2; border-radius: 10px; padding: 8px;")
        left.addWidget(tips)
        left.addStretch(1)
        btns = QHBoxLayout()
        code = QPushButton("Send code to editor")
        code.setProperty("class", "Teal")
        code.clicked.connect(self._emit_code)
        btns.addWidget(code)
        left.addLayout(btns)

        leftw = QWidget()
        leftw.setLayout(left)
        leftw.setFixedWidth(430)
        root.addWidget(leftw)

        right = QVBoxLayout()
        cards = QHBoxLayout()
        self.c_tr = metric_card("Rise time  زمن الصعود", PALETTE[0])
        self.c_ts = metric_card("Settling time  زمن الاستقرار", PALETTE[2])
        self.c_os = metric_card("Overshoot  التجاوز", PALETTE[3])
        self.c_ess = metric_card("Steady-state error  الخطأ المستقر", PALETTE[1])
        for c in (self.c_tr, self.c_ts, self.c_os, self.c_ess):
            cards.addWidget(c)
        right.addLayout(cards)
        self.status = banner()
        right.addWidget(self.status)
        self.fig, self.canvas = make_canvas()
        right.addWidget(self.canvas, 1)
        root.addLayout(right, 1)

        self.num.editingFinished.connect(self.schedule)
        self.den.editingFinished.connect(self.schedule)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.update_plot)
        self.update_plot()

    def _load_ws(self, name):
        v = self.workspace.get(name)
        if isinstance(v, TransferFunction):
            self.num.setText(" ".join(f"{x:g}" for x in v.num))
            self.den.setText(" ".join(f"{x:g}" for x in v.den))
            self.schedule()

    def _type_changed(self, t):
        self.ki.set_enabled("I" in t)
        self.kd.set_enabled("D" in t)
        self.schedule()

    def schedule(self):
        self.timer.start()

    def plant(self):
        return TransferFunction(parse_poly(self.num.text()), parse_poly(self.den.text()))

    def gains(self):
        t = self.ctype.currentText()
        return (self.kp.value(), self.ki.value() if "I" in t else 0.0, self.kd.value() if "D" in t else 0.0)

    def update_plot(self):
        try:
            G = self.plant()
        except Exception:
            set_banner(self.status, "bad", "Invalid plant coefficients  —  معاملات النظام غير صحيحة")
            return
        label = "G(s) = " + tf_label(G)
        if getattr(self, "zn_note", None) and getattr(self, "zn_plant", None) == label:
            label += "\n" + self.zn_note
        else:
            self.zn_note = None
        self.zn_plant = label.split("\n")[0]
        self.plant_lbl.setText(label)
        kp, ki, kd = self.gains()
        Cs = pid(kp, ki, kd)
        T = feedback(Cs * G, 1)
        T0 = feedback(G, 1)
        fig = self.fig
        fig.clear()
        ax = fig.add_subplot(111)
        style_axes(ax)
        stable = np.all(T.poles().real < 0)
        try:
            if stable:
                t = an.auto_time(T)
                t0 = an.auto_time(T0)
                tf_ = min(max(t[-1], t0[-1] if np.all(T0.poles().real < 0) else t[-1]), t[-1] * 4)
                t = np.linspace(0, tf_, 1200)
            else:
                t = np.linspace(0, 5, 800)
            _, y0 = an.step_response(T0, t)
            _, y = an.step_response(T, t)
            if T.is_proper():
                ax.plot(t, y0, color="#9AA8BA", linestyle="--", linewidth=1.4, label="Without controller (P = 1)")
            ax.plot(t, y, color=PALETTE[0], linewidth=2.2, label=f"With {self.ctype.currentText()}")
            ax.axhline(1, color="#00BFA5", linestyle=":", linewidth=1)
            if stable:
                ylim = ax.get_ylim()
                ax.set_ylim(min(0, ylim[0]), max(ylim[1], 1.15))
        except ValueError:
            pass
        ax.set_title("Closed-loop step response  T(s) = CG / (1 + CG)", fontsize=11, fontweight="bold")
        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Amplitude")
        ax.grid(True, color="#E3EBF5")
        ax.legend(fontsize=9)
        apply_theme(self.fig)
        self.canvas.draw_idle()

        if not stable:
            for c in (self.c_tr, self.c_ts, self.c_os, self.c_ess):
                c.value.setText("—")
            set_banner(self.status, "bad", "UNSTABLE closed loop  —  نظام الحلقة المغلقة غير مستقر")
            return
        info = an.system_step_info(T)
        dc = T.dcgain()
        ess = abs(1 - dc) if np.isfinite(dc) else np.inf
        self.c_tr.value.setText(f"{info['RiseTime']:.3g} s")
        self.c_ts.value.setText(f"{info['SettlingTime']:.3g} s")
        self.c_os.value.setText(f"{info['Overshoot']:.3g} %")
        self.c_ess.value.setText(f"{ess:.3g}")
        if info["Overshoot"] < 10 and ess < 0.02:
            set_banner(self.status, "ok", "Stable with good response  —  النظام مستقر واستجابته جيدة")
        else:
            set_banner(self.status, "warn", "Stable — keep tuning to reduce overshoot / error  —  النظام مستقر، ويمكن تحسين أدائه")

    def ziegler_nichols(self):
        try:
            G = self.plant()
        except Exception:
            return
        kind = self.ctype.currentText()
        if kind == "PD":
            kind = "PID"
            self.ctype.setCurrentText("PID")
        Kcr, Pcr = an.zn_ultimate(G)
        if Kcr is not None:
            Kp, Ti, Td = an.zn_table(kind, 2, Kcr, Pcr)
            note = f"Z-N method 2:  Kcr = {Kcr:.4g},  Pcr = {Pcr:.4g} s"
        else:
            K, L, T = an.zn_step_parameters(G)
            if K is None or not L:
                set_banner(self.status, "warn", "Ziegler-Nichols does not apply to this plant  —  "
                                                "لا تنطبق هذه الطريقة على هذا النظام")
                return
            Kp, Ti, Td = an.zn_table(kind, 1, L, T)
            note = f"Z-N method 1:  L = {L:.4g} s,  T = {T:.4g} s"
        for gc, v in ((self.kp, Kp), (self.ki, 0 if np.isinf(Ti) else Kp / Ti), (self.kd, Kp * Td)):
            if v > gc.maxspin.value():
                gc.maxspin.setValue(v * 2)
            gc.set_value(round(v, 4))
        self.zn_note = note
        self.update_plot()

    def auto_tune(self):
        from scipy.optimize import minimize
        try:
            G = self.plant()
        except Exception:
            return
        t_type = self.ctype.currentText()
        t = np.linspace(0, max(an.auto_time(feedback(G, 1))[-1], 2.0) * 1.5, 500) \
            if np.all(feedback(G, 1).poles().real < 0) else np.linspace(0, 10, 500)

        def cost(x):
            kp, ki, kd = np.exp(x)
            ki = ki if "I" in t_type else 0
            kd = kd if "D" in t_type else 0
            T = feedback(pid(kp, ki, kd) * G, 1)
            if not np.all(T.poles().real < -1e-6) or not T.is_proper():
                return 1e9
            try:
                _, y = an.step_response(T, t)
            except ValueError:
                return 1e9
            e = np.abs(1 - y)
            os_ = max(0.0, y.max() - 1)
            return float(np.trapezoid(t * e, t) + 50 * os_ ** 2 + 1e-4 * (kp + ki + kd))
        x0 = np.log(np.maximum([self.kp.value() or 1, self.ki.value() or 1, self.kd.value() or 0.1], 1e-3))
        res = minimize(cost, x0, method="Nelder-Mead", options={"maxiter": 400, "xatol": 1e-3, "fatol": 1e-4})
        kp, ki, kd = np.exp(res.x)
        self.kp.set_value(round(kp, 3))
        if "I" in t_type:
            self.ki.set_value(round(ki, 3))
        if "D" in t_type:
            self.kd.set_value(round(kd, 3))
        self.update_plot()

    def _emit_code(self):
        kp, ki, kd = self.gains()
        code = (f"% PID design generated by the PID Tuner\n"
                f"G = tf([{self.num.text()}], [{self.den.text()}]);   % plant\n"
                f"C = pid({kp:g}, {ki:g}, {kd:g});                     % controller\n"
                f"T = feedback(C*G, 1);                                 % closed loop\n"
                f"step(feedback(G, 1), T); legend('Without controller', 'With {self.ctype.currentText()}')\n"
                f"S = stepinfo(T)\n")
        self.send_code.emit(code)


# ---------------------------------------------------------------------------
# Routh-Hurwitz analyzer
# ---------------------------------------------------------------------------

class RouthTool(ToolDialog):
    def __init__(self, parent=None):
        super().__init__("Routh-Hurwitz Stability  —  معيار راوث للاستقرارية", parent)
        root = QHBoxLayout(self)
        root.setSpacing(12)
        left = QVBoxLayout()

        gb = QGroupBox("Characteristic equation  —  المعادلة المميزة")
        g = QGridLayout(gb)
        self.mode = QComboBox()
        self.mode.addItems(["Polynomial coefficients  a_n ... a_0", "Closed loop  1 + K·G(s) = 0"])
        self.mode.currentIndexChanged.connect(self._mode_changed)
        g.addWidget(self.mode, 0, 0, 1, 2)
        self.poly = QLineEdit("1 2 3 4 5")
        self.l_poly = QLabel("coefficients:")
        g.addWidget(self.l_poly, 1, 0)
        g.addWidget(self.poly, 1, 1)
        self.num = QLineEdit("1")
        self.den = QLineEdit("1 3 2 0")
        self.l_num, self.l_den = QLabel("G num:"), QLabel("G den:")
        g.addWidget(self.l_num, 2, 0)
        g.addWidget(self.num, 2, 1)
        g.addWidget(self.l_den, 3, 0)
        g.addWidget(self.den, 3, 1)
        self.k = QDoubleSpinBox()
        self.k.setRange(0, 1e6)
        self.k.setDecimals(3)
        self.k.setValue(4)
        self.k.setPrefix("K = ")
        self.l_k = QLabel("gain:")
        g.addWidget(self.l_k, 4, 0)
        g.addWidget(self.k, 4, 1)
        go = QPushButton("Analyze  -  تحليل")
        go.clicked.connect(self.analyze)
        g.addWidget(go, 5, 0, 1, 2)
        left.addWidget(gb)

        self.eq = QLabel()
        self.eq.setWordWrap(True)
        set_css(self.eq, "font-family: 'JetBrains Mono', Consolas; font-size: 10.5pt; color: #1565C0; padding: 4px;")
        left.addWidget(self.eq)
        self.verdict = banner()
        left.addWidget(self.verdict)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.TextFormat.RichText)
        set_css(self.info, "background: white; border: 1px solid #DCE6F2; border-radius: 10px; padding: 8px;")
        left.addWidget(self.info)
        left.addStretch(1)
        code = QPushButton("Send code to editor")
        code.setProperty("class", "Teal")
        code.clicked.connect(self._emit_code)
        left.addWidget(code)
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(420)
        root.addWidget(lw)

        right = QVBoxLayout()
        title = QLabel("Routh array  —  جدول راوث   (first column is highlighted)")
        title.setProperty("class", "PanelTitle")
        right.addWidget(title)
        self.table = QTableWidget()
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right.addWidget(self.table, 3)
        self.fig, self.canvas = make_canvas(3.0)
        right.addWidget(self.canvas, 2)
        root.addLayout(right, 1)
        for w in (self.poly, self.num, self.den):
            w.returnPressed.connect(self.analyze)
        self.k.valueChanged.connect(self.analyze)
        self._mode_changed(0)

    def _mode_changed(self, idx):
        closed = idx == 1
        for w in (self.l_num, self.l_den, self.num, self.den, self.k, self.l_k):
            w.setVisible(closed)
        self.poly.setVisible(not closed)
        self.l_poly.setVisible(not closed)
        self.analyze()

    def coefficients(self):
        if self.mode.currentIndex() == 0:
            return parse_poly(self.poly.text()), None
        G = TransferFunction(parse_poly(self.num.text()), parse_poly(self.den.text()))
        return an._char_poly(G.num, G.den, self.k.value()), G

    def analyze(self):
        try:
            p, G = self.coefficients()
            T, notes, changes = an.routh_array(p)
        except Exception as e:
            set_banner(self.verdict, "bad", f"Invalid input: {e}")
            return
        n = T.shape[0] - 1
        self.eq.setText("Δ(s) = " + poly_to_str(p) + " = 0")
        self.table.clear()
        self.table.setRowCount(T.shape[0])
        self.table.setColumnCount(T.shape[1])
        self.table.setHorizontalHeaderLabels([f"col {j + 1}" for j in range(T.shape[1])])
        self.table.setVerticalHeaderLabels([f"s^{n - i}" for i in range(T.shape[0])])
        special_rows = {i for _, i, _ in notes}
        for i in range(T.shape[0]):
            for j in range(T.shape[1]):
                x = T[i, j]
                item = QTableWidgetItem(f"{x:.5g}" if abs(x) > 1e-12 or j == 0 else "0")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 0:
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                    item.setBackground(qc("#E8F8F0" if x > 0 else "#FDECEF" if x < 0 else "#FFF6E5"))
                    item.setForeground(qc("#2E7D32" if x > 0 else "#C62828"))
                elif i in special_rows:
                    item.setBackground(qc("#FFF6E5"))
                self.table.setItem(i, j, item)
        has_zero_row = any(k == "zero_row" for k, _, _ in notes)
        if changes:
            set_banner(self.verdict, "bad", f"UNSTABLE — {changes} pole(s) in the RHP\n"
                                            f"النظام غير مستقر — عدد الجذور في النصف الأيمن: {changes}")
        elif has_zero_row:
            set_banner(self.verdict, "warn", "MARGINALLY STABLE — poles on the jω axis\nالنظام على حافة الاستقرار — توجد جذور على المحور التخيلي")
        else:
            set_banner(self.verdict, "ok", "STABLE — all poles in the LHP\nالنظام مستقر — جميع الجذور في النصف الأيسر")
        r = an.roots(p)
        lines = [f"<b>Sign changes:</b> {changes}"]
        for kind, i, aux in notes:
            if kind == "zero_first":
                lines.append(f"<span style='color:#E65100'>Row s^{n - i}: first element = 0, replaced by ε</span>")
            else:
                lines.append(f"<span style='color:#E65100'>Row s^{n - i}: all zeros, auxiliary polynomial "
                             f"A(s) = {poly_to_str(aux)}; row replaced by dA/ds</span>")
        lines.append("<b>Roots (check):</b> " + ", ".join(
            f"{z.real:.4g}{'' if abs(z.imag) < 1e-9 else f'{z.imag:+.4g}j'}" for z in r))
        if G is not None:
            crossings = an.imag_axis_crossings(G)
            kr = [k for k, _ in crossings]
            if kr:
                lines.append(f"<b>Critical gain:</b> K = {min(kr):.5g} at ω = "
                             f"{[w for k, w in crossings if k == min(kr)][0]:.4g} rad/s")
        self.info.setText(themed("<br>".join(lines)))

        fig = self.fig
        fig.clear()
        ax = fig.add_subplot(111)
        style_axes(ax)
        ax.axvspan(0, max(1.0, np.max(np.abs(r.real)) * 1.4 if r.size else 1), color="#FDECEF", zorder=0)
        ax.axhline(0, color="#B8C7D9", linewidth=0.8)
        ax.axvline(0, color="#C62828", linewidth=1, linestyle="--")
        colors = ["#C62828" if z.real > 1e-9 else "#E65100" if abs(z.real) <= 1e-9 else "#2E7D32" for z in r]
        ax.scatter(r.real, r.imag, marker="x", s=80, c=colors, linewidths=2.4, zorder=3)
        span = max(np.max(np.abs(r)) if r.size else 1, 1) * 1.4
        ax.set_xlim(-span, span)
        ax.set_ylim(-span, span)
        ax.set_title("Roots in the s-plane (red region = unstable)", fontsize=10, fontweight="bold")
        ax.grid(True, color="#E3EBF5")
        apply_theme(self.fig)
        self.canvas.draw_idle()

    def _emit_code(self):
        p, G = self.coefficients()
        coeffs = " ".join(f"{x:g}" for x in p)
        code = f"% Routh-Hurwitz test\np = [{coeffs}];\nrouth(p)\nroots(p)\n"
        if G is not None:
            code += (f"G = tf([{self.num.text()}], [{self.den.text()}]);\n"
                     f"krange(G)      % range of K for stability\nrlocus(G); sgrid\n")
        self.send_code.emit(code)


# ---------------------------------------------------------------------------
# Block diagram builder
# ---------------------------------------------------------------------------

TOPOLOGIES = [
    ("Series:  G1 · G2", "series"),
    ("Parallel:  G1 + G2", "parallel"),
    ("Feedback:  G / (1 + G·H)", "feedback"),
    ("Controller + Plant:  C·G / (1 + C·G·H)", "loop"),
]


class DiagramView(QWidget):
    def __init__(self):
        super().__init__()
        self.kind = "loop"
        self.labels = {}
        self.setMinimumHeight(220)

    def set_kind(self, kind, labels):
        self.kind = kind
        self.labels = labels
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qc("white"))
        w, h = self.width(), self.height()
        cy = h * 0.42
        pen = QPen(qc("#24324A"), 2)
        p.setPen(pen)
        font = QFont("Segoe UI", 10)
        p.setFont(font)

        def block(x, y, name, color):
            bw, bh = 120, 54
            rect = QRectF(x - bw / 2, y - bh / 2, bw, bh)
            p.setBrush(QBrush(qc(color).darker(260) if is_dark() else qc(color).lighter(185)))
            p.setPen(QPen(qc(color), 2.4))
            p.drawRoundedRect(rect, 12, 12)
            p.setPen(qc("#24324A"))
            f = QFont("Segoe UI", 12, QFont.Weight.Bold)
            p.setFont(f)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, name)
            p.setFont(font)
            sub = self.labels.get(name, "")
            if sub:
                p.setPen(qc("#6B7C93"))
                p.drawText(QRectF(x - 110, y + bh / 2 + 2, 220, 18), Qt.AlignmentFlag.AlignCenter, sub)
            p.setPen(pen)
            return rect

        def arrow(x1, y1, x2, y2):
            p.setPen(QPen(qc("#24324A"), 2))
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            ang = np.arctan2(y2 - y1, x2 - x1)
            a = 9
            pts = [QPointF(x2, y2),
                   QPointF(x2 - a * np.cos(ang - 0.4), y2 - a * np.sin(ang - 0.4)),
                   QPointF(x2 - a * np.cos(ang + 0.4), y2 - a * np.sin(ang + 0.4))]
            path = QPainterPath(pts[0])
            path.lineTo(pts[1])
            path.lineTo(pts[2])
            path.closeSubpath()
            p.setBrush(qc("#24324A"))
            p.drawPath(path)

        def summer(x, y, signs):
            p.setBrush(qc("#FFF6E5"))
            p.setPen(QPen(qc("#FF8F00"), 2.2))
            p.drawEllipse(QPointF(x, y), 15, 15)
            p.setPen(qc("#24324A"))
            p.drawText(QRectF(x - 30, y - 30, 20, 16), Qt.AlignmentFlag.AlignCenter, signs[0])
            p.drawText(QRectF(x + 2, y + 14, 20, 16), Qt.AlignmentFlag.AlignCenter, signs[1])
            p.setPen(pen)

        def label(x, y, t):
            p.setPen(qc("#1565C0"))
            p.drawText(QRectF(x - 40, y - 24, 80, 18), Qt.AlignmentFlag.AlignCenter, t)
            p.setPen(pen)

        k = self.kind
        if k == "series":
            x0, x1, x2, x3 = w * 0.08, w * 0.35, w * 0.65, w * 0.92
            block(x1, cy, "G1", PALETTE[0])
            block(x2, cy, "G2", PALETTE[2])
            arrow(x0, cy, x1 - 60, cy)
            arrow(x1 + 60, cy, x2 - 60, cy)
            arrow(x2 + 60, cy, x3, cy)
            label(x0 + 20, cy, "R(s)")
            label(x3 - 20, cy, "Y(s)")
        elif k == "parallel":
            xs, xb, xm, xe = w * 0.08, w * 0.25, w * 0.5, w * 0.78
            y1, y2 = cy - 55, cy + 45
            block(xm, y1, "G1", PALETTE[0])
            block(xm, y2, "G2", PALETTE[2])
            arrow(xs, cy, xb, cy)
            p.drawLine(QPointF(xb, y1), QPointF(xb, y2))
            arrow(xb, y1, xm - 60, y1)
            arrow(xb, y2, xm - 60, y2)
            p.drawLine(QPointF(xm + 60, y1), QPointF(xe, y1))
            p.drawLine(QPointF(xm + 60, y2), QPointF(xe, y2))
            arrow(xe, y1, xe, cy - 15)
            arrow(xe, y2, xe, cy + 15)
            summer(xe, cy, ("+", "+"))
            arrow(xe + 15, cy, w * 0.95, cy)
            label(xs + 20, cy, "R(s)")
            label(w * 0.92, cy, "Y(s)")
        else:
            loop = k == "loop"
            xs = w * 0.06
            xsum = w * 0.2
            xc = w * 0.4 if loop else w * 0.5
            xg = w * 0.66
            xo = w * 0.84
            xe = w * 0.95
            yb = cy + 85
            summer(xsum, cy, ("+", "−"))
            arrow(xs, cy, xsum - 15, cy)
            if loop:
                block(xc, cy, "C", PALETTE[4])
                arrow(xsum + 15, cy, xc - 60, cy)
                block(xg, cy, "G", PALETTE[0])
                arrow(xc + 60, cy, xg - 60, cy)
                p.drawLine(QPointF(xg + 60, cy), QPointF(xo, cy))
            else:
                block(xc, cy, "G", PALETTE[0])
                arrow(xsum + 15, cy, xc - 60, cy)
                p.drawLine(QPointF(xc + 60, cy), QPointF(xo, cy))
            arrow(xo, cy, xe, cy)
            p.setBrush(qc("#24324A"))
            p.drawEllipse(QPointF(xo, cy), 3.5, 3.5)
            hx = (xsum + xo) / 2
            block(hx, yb, "H", PALETTE[1])
            p.drawLine(QPointF(xo, cy), QPointF(xo, yb))
            arrow(xo, yb, hx + 60, yb)
            p.drawLine(QPointF(hx - 60, yb), QPointF(xsum, yb))
            arrow(xsum, yb, xsum, cy + 15)
            label(xs + 22, cy, "R(s)")
            label(xsum + 45, cy, "E(s)")
            label(xe - 14, cy, "Y(s)")


class BlockDiagramTool(ToolDialog):
    def __init__(self, parent=None):
        super().__init__("Block Diagram Builder  —  المخطط الصندوقي", parent)
        root = QHBoxLayout(self)
        root.setSpacing(12)
        left = QVBoxLayout()
        self.topo = QComboBox()
        for name, key in TOPOLOGIES:
            self.topo.addItem(name, key)
        self.topo.setCurrentIndex(3)
        self.topo.currentIndexChanged.connect(self.update_all)
        left.addWidget(self.topo)
        gb = QGroupBox("Blocks  —  الكتل   (num / den coefficients)")
        g = QGridLayout(gb)
        defaults = {"G1": ("1", "1 2"), "G2": ("1", "1 5"), "C": ("2 1", "1 0"),
                    "G": ("10", "1 3 2"), "H": ("1", "1")}
        self.fields = {}
        for r, (name, (n, d)) in enumerate(defaults.items()):
            lab = QLabel(name)
            set_css(lab, "font-weight: 700; font-size: 11pt;")
            ne, de = QLineEdit(n), QLineEdit(d)
            ne.setPlaceholderText("num")
            de.setPlaceholderText("den")
            ne.editingFinished.connect(self.update_all)
            de.editingFinished.connect(self.update_all)
            g.addWidget(lab, r, 0)
            g.addWidget(ne, r, 1)
            g.addWidget(QLabel("/"), r, 2)
            g.addWidget(de, r, 3)
            self.fields[name] = (lab, ne, de)
        left.addWidget(gb)
        self.result = QLabel()
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        set_css(self.result, "background: #F3F8FF; border: 1px solid #DCE6F2; border-radius: 10px;"
                                  " padding: 10px; font-family: 'JetBrains Mono', Consolas; font-size: 10.5pt;")
        left.addWidget(self.result)
        self.verdict = banner()
        left.addWidget(self.verdict)
        left.addStretch(1)
        code = QPushButton("Send code to editor")
        code.setProperty("class", "Teal")
        code.clicked.connect(self._emit_code)
        left.addWidget(code)
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(440)
        root.addWidget(lw)

        right = QVBoxLayout()
        self.diagram = DiagramView()
        frame = QFrame()
        frame.setProperty("class", "Card")
        fl = QVBoxLayout(frame)
        fl.addWidget(self.diagram)
        right.addWidget(frame, 2)
        self.fig, self.canvas = make_canvas(3.2)
        right.addWidget(self.canvas, 3)
        root.addLayout(right, 1)
        self.update_all()

    def tf(self, name):
        _, ne, de = self.fields[name]
        return TransferFunction(parse_poly(ne.text()), parse_poly(de.text()))

    def compute(self):
        k = self.topo.currentData()
        if k == "series":
            return self.tf("G1") * self.tf("G2")
        if k == "parallel":
            return self.tf("G1") + self.tf("G2")
        if k == "feedback":
            return feedback(self.tf("G"), self.tf("H"))
        return feedback(self.tf("C") * self.tf("G"), self.tf("H"))

    def used_blocks(self):
        return {"series": ["G1", "G2"], "parallel": ["G1", "G2"], "feedback": ["G", "H"],
                "loop": ["C", "G", "H"]}[self.topo.currentData()]

    def update_all(self):
        used = self.used_blocks()
        for name, widgets in self.fields.items():
            for w in widgets:
                w.setEnabled(name in used)
        try:
            labels = {n: tf_label(self.tf(n)) for n in used}
            T = self.compute()
        except Exception as e:
            set_banner(self.verdict, "bad", f"Invalid block: {e}")
            return
        self.diagram.set_kind(self.topo.currentData(), labels)
        p = T.poles()
        self.result.setText("<b>T(s) =</b><br><pre style='margin:4px 0'>" + T.to_str() + "</pre>"
                            + "<b>Poles:</b> " + ", ".join(
                                f"{z.real:.4g}{'' if abs(z.imag) < 1e-9 else f'{z.imag:+.4g}j'}" for z in p))
        stable = np.all(p.real < 0)
        set_banner(self.verdict, "ok" if stable else "bad",
                   "STABLE  —  النظام مستقر" if stable else "UNSTABLE  —  النظام غير مستقر")
        fig = self.fig
        fig.clear()
        ax = fig.add_subplot(111)
        style_axes(ax)
        try:
            t, y = an.step_response(T, an.auto_time(T) if stable else np.linspace(0, 5, 600))
            ax.plot(t, y, color=PALETTE[0], linewidth=2)
            if stable:
                info = an.system_step_info(T)
                ax.axhline(T.dcgain(), color="#00BFA5", linestyle=":", linewidth=1)
                ax.set_title(f"Step response   (Mp = {info['Overshoot']:.3g}%,  Ts = {info['SettlingTime']:.3g} s)",
                             fontsize=10, fontweight="bold")
            else:
                ax.set_title("Step response (unstable)", fontsize=10, fontweight="bold")
        except ValueError as e:
            ax.set_title(str(e), fontsize=9)
        ax.set_xlabel("Time (seconds)")
        ax.grid(True, color="#E3EBF5")
        apply_theme(self.fig)
        self.canvas.draw_idle()

    def _emit_code(self):
        lines = ["% Block diagram reduction"]
        for n in self.used_blocks():
            _, ne, de = self.fields[n]
            lines.append(f"{n} = tf([{ne.text()}], [{de.text()}]);")
        k = self.topo.currentData()
        lines.append({"series": "T = series(G1, G2)", "parallel": "T = parallel(G1, G2)",
                      "feedback": "T = feedback(G, H)", "loop": "T = feedback(C*G, H)"}[k])
        lines += ["pole(T)", "step(T); grid on", "S = stepinfo(T)"]
        self.send_code.emit("\n".join(lines) + "\n")
