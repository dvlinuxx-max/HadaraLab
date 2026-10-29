"""HadaraLab main window."""

import os
import sys
import threading
import time

from PySide6.QtCore import QDir, QObject, QProcess, QSize, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (QApplication, QFileDialog, QFileSystemModel, QFrame,
                               QGridLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QPushButton,
                               QScrollArea, QSplitter, QTabWidget, QToolButton,
                               QTreeView, QVBoxLayout, QWidget)

from .. import __version__
from ..engine import Interpreter, MatlabError
from ..engine.builtins import BUILTINS, HELP
from .console import CommandWindow
from .editor import CodeEditor
from .figures import FigurePanel
from .theme import C, asset, qc, save_theme, set_css, theme_name, themed
from .tools import BlockDiagramTool, PIDTuner, RouthTool
from .workspace import WorkspaceView

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# default working folder for the user's scripts
WORKDIR = os.path.join(os.path.expanduser("~"), "Documents", "HadaraLab")
os.makedirs(WORKDIR, exist_ok=True)

# shown by Help > Privacy and Notices (same content as PRIVACY.md)
PRIVACY_HTML = """
<div dir='rtl' style='font-size:10.5pt; line-height:160%'>
<h2 style='color:#1565C0'>سياسة الخصوصية</h2>
<p>يعمل برنامج HadaraLab بالكامل على جهاز المستخدم:</p>
<ol>
<li><b>لا يجمع البرنامج أي بيانات شخصية</b>، ولا يطلب إنشاء حساب أو تسجيل دخول.</li>
<li><b>لا يتصل البرنامج بالإنترنت</b>، ولا يرسل أي بيانات أو إحصاءات استخدام أو تقارير أعطال إلى أي جهة.</li>
<li><b>الملفات التي ينشئها المستخدم</b> (النصوص البرمجية وصور الرسوم البيانية) تُحفظ على جهازه فقط،
في المكان الذي يختاره بنفسه، والمجلد الافتراضي هو Documents\\HadaraLab.</li>
<li><b>الإعدادات:</b> يحفظ البرنامج إعداداً واحداً فقط هو المظهر المختار، ويُخزَّن محلياً في سجل نظام Windows.</li>
<li><b>الروابط الخارجية:</b> لا يُفتح الموقع الإلكتروني أو البريد الإلكتروني إلا إذا نقر المستخدم عليهما بنفسه.</li>
<li><b>حذف البيانات:</b> يكفي حذف مجلد البرنامج والمجلد Documents\\HadaraLab
ومفتاح السجل HKEY_CURRENT_USER\\Software\\Hadara\\HadaraLab.</li>
</ol>
<h2 style='color:#1565C0'>إشعار بشأن شعار الكلية واسمها</h2>
<ul>
<li><b>شعار كلية الحضارة الجامعة واسمها</b> ملكٌ لكلية الحضارة الجامعة.</li>
<li>يُستخدم الشعار والاسم في هذا البرنامج <b>لأغراض هذا المشروع البرمجي فقط</b>،
بوصفه مشروعاً تابعاً لقسم هندسة تقنيات الحاسوب في الكلية.</li>
<li><b>لا تشمل رخصة MIT</b> الخاصة بالشيفرة المصدرية شعارَ الكلية ولا اسمها.</li>
<li>لا يجوز استخدام الشعار أو الاسم أو نسخهما أو تعديلهما أو توزيعهما خارج هذا المشروع
إلا بإذن مسبق من كلية الحضارة الجامعة.</li>
</ul>
<p>للتواصل: <a href='mailto:support@mohmadev.com'>support@mohmadev.com</a> —
<a href='https://mohmadev.com/'>mohmadev.com</a></p>
</div>
<hr>
<div style='font-size:9.5pt; color:#4A5B73'>
<h3>Privacy policy</h3>
<p>HadaraLab runs entirely on your computer. It collects no personal data, needs no account,
never connects to the internet and sends no data, statistics or crash reports. Your scripts and
figures stay where you save them (default folder: Documents\\HadaraLab). Only the chosen theme is
stored, locally in the Windows registry. Links open only when you click them.</p>
<h3>Logo and name notice</h3>
<p>The logo and name of Al-Hadara University College belong to the college and are used solely
for this software project. They are not covered by the MIT License of the source code and may not
be used outside this project without the college's prior permission.</p>
</div>
"""


# ---------------------------------------------------------------------------
# threading helpers
# ---------------------------------------------------------------------------

class Bridge(QObject):
    text = Signal(str)
    clc = Signal()
    ask = Signal(str)


class RunWorker(QObject):
    finished = Signal(object, float)

    def __init__(self, interp, code):
        super().__init__()
        self.interp = interp
        self.code = code

    @Slot()
    def run(self):
        t0 = time.perf_counter()
        err = None
        try:
            self.interp.execute(self.code)
        except MatlabError as e:
            err = e
        except RecursionError:
            err = MatlabError("Maximum recursion limit reached.")
        except Exception as e:  # unexpected internal error: report, don't crash
            err = MatlabError(f"Internal error: {type(e).__name__}: {e}")
        self.finished.emit(err, time.perf_counter() - t0)


# ---------------------------------------------------------------------------
# editor tab & start page
# ---------------------------------------------------------------------------

class EditorTab(QWidget):
    def __init__(self, path=None, text="", parent=None):
        super().__init__(parent)
        self.path = path
        self.editor = CodeEditor(sorted(BUILTINS))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.editor)
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)

    def title(self):
        name = os.path.basename(self.path) if self.path else getattr(self, "untitled", "untitled.m")
        return name + (" •" if self.editor.document().isModified() else "")


def _card_button(title, subtitle, color, slot):
    b = QPushButton()
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setMinimumHeight(78)
    set_css(b, 
        f"QPushButton {{ background: white; border: 1px solid {C['border']}; border-left: 5px solid {color};"
        f" border-radius: 14px; text-align: left; padding: 10px 14px; color: {C['text']}; }}"
        f"QPushButton:hover {{ background: #F5FAFF; border-color: {color}; }}")
    lay = QHBoxLayout(b)
    lay.setContentsMargins(16, 8, 14, 8)
    txt = QLabel(themed(f"<div style='font-size:11.5pt; font-weight:700; color:{color}'>{title}</div>"
                        f"<div style='font-size:9pt; color:#6B7C93'>{subtitle}</div>"))
    set_css(txt, "background: transparent; border: none;")
    txt.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    lay.addWidget(txt, 1)
    b.clicked.connect(slot)
    return b


class StartPage(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.setWidgetResizable(True)
        set_css(self, "QScrollArea { border: none; background: white; }")
        body = QWidget()
        set_css(body, "background: white;")
        self.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(14)

        hero = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(asset("logo_256.png")).scaled(
            110, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        hero.addWidget(logo)
        txt = QLabel(themed(
            f"<div style='font-size:24pt; font-weight:800; color:{C['primary_dark']}'>HadaraLab"
            f"<span style='font-size:11pt; color:{C['teal']}; font-weight:600'>  v{__version__}</span></div>"))
        txt.setWordWrap(True)
        hero.addWidget(txt, 1)
        lay.addLayout(hero)

        grid = QGridLayout()
        grid.setSpacing(12)
        cards = [
            ("New Script", "نص برمجي جديد  (Ctrl+N)", C["primary"], win.new_tab),
            ("Open File", "فتح ملف .m  (Ctrl+O)", C["teal"], win.open_file),
            ("PID Tuner", "ضبط متحكم PID تفاعلياً", C["purple"], win.open_pid),
            ("Routh Table", "فحص الاستقرارية بمعيار راوث", C["orange"], win.open_routh),
            ("Block Diagram", "تبسيط المخططات الصندوقية", C["pink"], win.open_blocks),
            ("Function Help", "قائمة الدوال المتاحة", C["green"], win.show_functions),
        ]
        for i, (t, s, col, slot) in enumerate(cards):
            grid.addWidget(_card_button(t, s, col, slot), i // 3, i % 3)
        lay.addLayout(grid)

        keys = QLabel(
            "<b>Shortcuts:</b>  F5 run script  ·  F9 run selection  ·  Ctrl+/ comment  ·  "
            "Ctrl+S save  ·  Up/Down command history  ·  Tab completion")
        keys.setWordWrap(True)
        set_css(keys, "background: #F3F8FF; border: 1px solid #DCE6F2; border-radius: 10px; padding: 10px;"
                           " color: #4A5B73;")
        lay.addWidget(keys)
        lay.addStretch(1)


# ---------------------------------------------------------------------------
# main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HadaraLab")
        self.setWindowIcon(QIcon(asset("app_icon.ico")))
        self.resize(1500, 920)
        self.untitled_count = 0
        self.running = False
        self.thread = None
        self.worker = None
        self.tools = []
        self.run_source = None

        self.bridge = Bridge()
        self.interp = Interpreter(output=self.bridge.text.emit)
        self.interp.cwd = WORKDIR
        self.interp.on_clc = self.bridge.clc.emit
        self._input_event = threading.Event()
        self._input_value = None
        self.interp.on_input = self._request_input

        self._build_ui()
        self._build_menu()
        self.bridge.text.connect(self.console.write)
        self.bridge.clc.connect(self.console.clear)
        self.bridge.ask.connect(self._ask_input)
        self.console.write_info(f"HadaraLab {__version__}  —  type  help  for the list of functions.\n")

    # -- layout --------------------------------------------------------------
    def _build_ui(self):
        self.status_label = QLabel("Ready")
        self.pos_label = QLabel("")
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.pos_label)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QWidget()
        bl = QHBoxLayout(body)
        bl.setContentsMargins(10, 10, 10, 6)
        main_split = QSplitter(Qt.Orientation.Horizontal)
        bl.addWidget(main_split)

        # left side panels
        self.left_tabs = QTabWidget()
        self.workspace = WorkspaceView()
        self.workspace.inspect.connect(lambda n: self.run_command(n, echo=True))
        self.left_tabs.addTab(self.workspace, "Workspace")
        self.left_tabs.addTab(self._build_files(), "Files")
        self.left_tabs.addTab(self._build_functions(), "Functions")
        main_split.addWidget(self.left_tabs)

        # center: editor + console
        center = QSplitter(Qt.Orientation.Vertical)
        self.editors = QTabWidget()
        self.editors.setTabsClosable(True)
        self.editors.setMovable(True)
        self.editors.tabCloseRequested.connect(self.close_tab)
        self.editors.currentChanged.connect(self._update_status)
        self.start_page = StartPage(self)
        self.editors.addTab(self.start_page, "Start")
        self.editors.tabBar().setTabButton(0, self.editors.tabBar().ButtonPosition.RightSide, None)
        center.addWidget(self.editors)

        cw = QWidget()
        cl = QVBoxLayout(cw)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)
        head = QHBoxLayout()
        lbl = QLabel("Command Window  —  نافذة الأوامر")
        lbl.setProperty("class", "PanelTitle")
        head.addWidget(lbl)
        head.addStretch(1)
        clear = QPushButton("Clear")
        clear.setProperty("class", "Secondary")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(lambda: self.console.clear())
        head.addWidget(clear)
        cl.addLayout(head)
        self.console = CommandWindow()
        self.console.command.connect(lambda c: self.run_command(c, echo=False))
        cl.addWidget(self.console)
        center.addWidget(cw)
        center.setSizes([560, 300])
        main_split.addWidget(center)

        # right: figures
        self.figures = FigurePanel()
        self.figures.figure_closed.connect(lambda n: self.interp.figures.close(n))
        main_split.addWidget(self.figures)
        main_split.setSizes([260, 680, 560])
        main_split.setStretchFactor(1, 1)
        main_split.setStretchFactor(2, 1)
        root.addWidget(body, 1)
        self.setCentralWidget(central)

    def _build_header(self):
        header = QWidget()
        header.setObjectName("Header")
        header.setFixedHeight(64)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(14, 6, 14, 6)
        lay.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(QPixmap(asset("logo_256.png")).scaled(
            48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        lay.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        t = QLabel("HadaraLab")
        t.setObjectName("AppTitle")
        titles.addWidget(t)
        lay.addLayout(titles)
        lay.addSpacing(18)

        def hbtn(text, tip, slot):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setProperty("class", "HeaderButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            lay.addWidget(b)
            return b

        hbtn("New", "New script (Ctrl+N)", self.new_tab)
        hbtn("Open", "Open .m file (Ctrl+O)", self.open_file)
        hbtn("Save", "Save (Ctrl+S)", self.save_file)
        lay.addSpacing(10)
        self.run_btn = QToolButton()
        self.run_btn.setObjectName("RunButton")
        self.run_btn.setText("Run")
        self.run_btn.setToolTip("Run the current script (F5)")
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.clicked.connect(self.run_script)
        lay.addWidget(self.run_btn)
        self.stop_btn = QToolButton()
        self.stop_btn.setObjectName("StopButton")
        self.stop_btn.setText("Stop")
        self.stop_btn.setToolTip("Stop execution")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        lay.addWidget(self.stop_btn)
        lay.addSpacing(10)
        hbtn("PID Tuner", "Interactive PID tuning", self.open_pid)
        hbtn("Routh", "Routh-Hurwitz stability table", self.open_routh)
        hbtn("Block Diagram", "Block diagram builder", self.open_blocks)
        lay.addStretch(1)
        hbtn("About", "About HadaraLab", self.about)
        return header

    def _build_files(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        self.fs_model = QFileSystemModel()
        self.fs_model.setNameFilters(["*.m"])
        self.fs_model.setNameFilterDisables(False)
        self.fs_model.setRootPath(WORKDIR)
        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setRootIndex(self.fs_model.index(WORKDIR))
        for c in (1, 2, 3):
            self.tree.hideColumn(c)
        self.tree.setHeaderHidden(True)
        self.tree.doubleClicked.connect(self._open_from_tree)
        self.folder_label = QLabel(self._short(WORKDIR))
        set_css(self.folder_label, "color: #6B7C93; font-size: 8.5pt;")
        self.folder_label.setWordWrap(True)
        change = QPushButton("Change folder…")
        change.setProperty("class", "Secondary")
        change.clicked.connect(self.change_folder)
        lay.addWidget(self.folder_label)
        lay.addWidget(self.tree, 1)
        lay.addWidget(change)
        return w

    def _build_functions(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        search = QLineEdit()
        search.setPlaceholderText("Search functions...  البحث عن دالة")
        self.fn_list = QListWidget()
        set_css(self.fn_list, "QListWidget::item { padding: 4px; }")
        cats = {}
        for name, (sig, en, ar, cat) in HELP.items():
            cats.setdefault(cat, []).append((name, sig, en, ar))
        order = ["Control", "Plotting", "Polynomials", "Math", "Matrix", "Linear algebra",
                 "Data", "Strings", "Functions", "Environment", "Constants"]
        for cat in order + sorted(set(cats) - set(order)):
            if cat not in cats:
                continue
            head = QListWidgetItem(f"— {cat} —")
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            head.setForeground(qc(C["primary_dark"]))
            f = head.font()
            f.setBold(True)
            head.setFont(f)
            self.fn_list.addItem(head)
            for name, sig, en, ar in sorted(cats[cat]):
                it = QListWidgetItem(f"  {name}")
                it.setToolTip(f"<b>{sig}</b><br>{en}<br><span dir='rtl'>{ar}</span>")
                it.setData(Qt.ItemDataRole.UserRole, (name, sig))
                if cat == "Control":
                    it.setForeground(qc("#D81B60"))
                self.fn_list.addItem(it)
        search.textChanged.connect(self._filter_functions)
        self.fn_list.itemDoubleClicked.connect(self._insert_function)
        self.fn_detail = QLabel("Double-click a function to insert it.\nانقر نقراً مزدوجاً لإدراج الدالة.")
        self.fn_detail.setWordWrap(True)
        set_css(self.fn_detail, "background: #F3F8FF; border: 1px solid #DCE6F2; border-radius: 8px;"
                                     " padding: 6px; font-size: 9pt;")
        self.fn_list.currentItemChanged.connect(self._show_function)
        lay.addWidget(search)
        lay.addWidget(self.fn_list, 1)
        lay.addWidget(self.fn_detail)
        return w

    def _build_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu("&File")
        self._act(fm, "New Script", self.new_tab, QKeySequence.StandardKey.New)
        self._act(fm, "Open…", self.open_file, QKeySequence.StandardKey.Open)
        self._act(fm, "Save", self.save_file, QKeySequence.StandardKey.Save)
        self._act(fm, "Save As…", self.save_file_as, QKeySequence("Ctrl+Shift+S"))
        fm.addSeparator()
        self._act(fm, "Exit", self.close, QKeySequence("Ctrl+Q"))
        em = mb.addMenu("&Edit")
        self._act(em, "Toggle Comment", lambda: self._editor() and self._editor().toggle_comment(),
                  QKeySequence("Ctrl+/"))
        self._act(em, "Clear Command Window", self.console_clear, None)
        self._act(em, "Clear Workspace", lambda: self.run_command("clear", echo=True), None)
        rm = mb.addMenu("&Run")
        self._act(rm, "Run Script", self.run_script, QKeySequence("F5"))
        self._act(rm, "Run Selection", self.run_selection, QKeySequence("F9"))
        self._act(rm, "Stop", self.stop, QKeySequence("Ctrl+Break"))
        self._act(rm, "Close All Figures", lambda: self.run_command("close all", echo=True), None)
        tm = mb.addMenu("&Tools")
        self._act(tm, "PID Tuner", self.open_pid, None)
        self._act(tm, "Routh-Hurwitz Table", self.open_routh, None)
        self._act(tm, "Block Diagram Builder", self.open_blocks, None)
        sm = mb.addMenu("&Settings")
        theme_menu = sm.addMenu("Theme  -  المظهر")
        group = QActionGroup(self)
        group.setExclusive(True)
        for key, label in (("light", "Light  -  فاتح"), ("dark", "Dark (Electric)  -  داكن")):
            a = QAction(label, self, checkable=True)
            a.setChecked(theme_name() == key)
            a.triggered.connect(lambda _=False, k=key: self.choose_theme(k))
            group.addAction(a)
            theme_menu.addAction(a)
        hm = mb.addMenu("&Help")
        self._act(hm, "Function List", self.show_functions, QKeySequence("F1"))
        self._act(hm, "Privacy and Notices  -  الخصوصية والإشعارات", self.show_privacy, None)
        self._act(hm, "About HadaraLab", self.about, None)

    def choose_theme(self, name):
        if name == theme_name():
            return
        save_theme(name)
        r = QMessageBox.question(
            self, "Theme",
            "The new theme will be applied after restarting HadaraLab.\nRestart now?\n\n"
            "سيُطبَّق المظهر الجديد بعد إعادة تشغيل البرنامج.\nهل تريد إعادة التشغيل الآن؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.restart()

    def restart(self):
        if not self.close():          # the user may cancel because of unsaved files
            return
        if getattr(sys, "frozen", False):
            QProcess.startDetached(sys.executable, sys.argv[1:])
        else:
            QProcess.startDetached(sys.executable, [os.path.abspath(sys.argv[0])] + sys.argv[1:])
        QApplication.quit()

    def _act(self, menu, text, slot, shortcut):
        a = QAction(text, self)
        if shortcut is not None:
            a.setShortcut(shortcut)
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    # -- helpers -------------------------------------------------------------
    def _short(self, path):
        return path if len(path) < 60 else "…" + path[-58:]

    def _tab(self):
        w = self.editors.currentWidget()
        return w if isinstance(w, EditorTab) else None

    def _editor(self):
        t = self._tab()
        return t.editor if t else None

    def _update_status(self, *_):
        ed = self._editor()
        if ed:
            c = ed.textCursor()
            self.pos_label.setText(f"Ln {c.blockNumber() + 1}, Col {c.columnNumber() + 1}   ")
        else:
            self.pos_label.setText("")

    def _refresh_tab_title(self, tab):
        i = self.editors.indexOf(tab)
        if i != -1:
            self.editors.setTabText(i, tab.title())
            self.editors.setTabToolTip(i, tab.path or "Unsaved script")

    def console_clear(self):
        self.console.clear()

    # -- files ---------------------------------------------------------------
    def new_tab(self, path=None, text=""):
        tab = EditorTab(path if isinstance(path, str) else None, text)
        if not tab.path:
            self.untitled_count += 1
            tab.untitled = f"untitled{self.untitled_count}.m"
            if not text:
                tab.editor.setPlainText("% New script\nclc; clear; close all\n\n")
                tab.editor.document().setModified(False)
                cur = tab.editor.textCursor()
                cur.movePosition(cur.MoveOperation.End)
                tab.editor.setTextCursor(cur)
        tab.editor.modified_changed.connect(lambda _m, t=tab: self._refresh_tab_title(t))
        tab.editor.cursorPositionChanged.connect(self._update_status)
        tab.editor.run_selection.connect(lambda code: self.run_command(code, echo=True))
        i = self.editors.addTab(tab, tab.title())
        self.editors.setCurrentIndex(i)
        self._refresh_tab_title(tab)
        tab.editor.setFocus()
        return tab

    def open_path(self, path):
        for i in range(self.editors.count()):
            w = self.editors.widget(i)
            if isinstance(w, EditorTab) and w.path and os.path.samefile(w.path, path):
                self.editors.setCurrentIndex(i)
                return w
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except UnicodeDecodeError:
            with open(path, encoding="latin-1") as fh:
                text = fh.read()
        return self.new_tab(path, text)

    def open_file(self):
        start = os.path.dirname(self._tab().path) if self._tab() and self._tab().path else self.interp.cwd
        path, _ = QFileDialog.getOpenFileName(self, "Open script", start, "MATLAB scripts (*.m);;All files (*)")
        if path:
            self.open_path(path)

    def _open_from_tree(self, index):
        path = self.fs_model.filePath(index)
        if os.path.isfile(path):
            self.open_path(path)

    def change_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Choose working folder", self.interp.cwd)
        if d:
            self.set_folder(d)

    def set_folder(self, d):
        self.interp.cwd = d
        self.fs_model.setRootPath(d)
        self.tree.setRootIndex(self.fs_model.index(d))
        self.folder_label.setText(self._short(d))

    def save_file(self):
        tab = self._tab()
        if not tab:
            return False
        if not tab.path:
            return self.save_file_as()
        with open(tab.path, "w", encoding="utf-8") as fh:
            fh.write(tab.editor.toPlainText())
        tab.editor.document().setModified(False)
        self._refresh_tab_title(tab)
        self.status_label.setText(f"Saved {tab.path}")
        return True

    def save_file_as(self):
        tab = self._tab()
        if not tab:
            return False
        start = tab.path or os.path.join(os.path.expanduser("~"), "Documents", tab.untitled)
        path, _ = QFileDialog.getSaveFileName(self, "Save script", start, "MATLAB scripts (*.m)")
        if not path:
            return False
        if not path.lower().endswith(".m"):
            path += ".m"
        tab.path = path
        return self.save_file()

    def close_tab(self, i):
        w = self.editors.widget(i)
        if not isinstance(w, EditorTab):
            return
        if w.editor.document().isModified():
            self.editors.setCurrentIndex(i)
            r = QMessageBox.question(self, "Unsaved changes", f"Save changes to {w.title().rstrip(' •')}?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                     QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Cancel:
                return
            if r == QMessageBox.StandardButton.Save and not self.save_file():
                return
        self.editors.removeTab(i)
        w.deleteLater()

    def closeEvent(self, e):
        for i in reversed(range(self.editors.count())):
            w = self.editors.widget(i)
            if isinstance(w, EditorTab) and w.editor.document().isModified():
                self.editors.setCurrentIndex(i)
                r = QMessageBox.question(self, "Unsaved changes",
                                         f"Save changes to {w.title().rstrip(' •')}?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                         QMessageBox.StandardButton.Cancel)
                if r == QMessageBox.StandardButton.Cancel:
                    e.ignore()
                    return
                if r == QMessageBox.StandardButton.Save and not self.save_file():
                    e.ignore()
                    return
        self.shutdown_threads()
        e.accept()

    def shutdown_threads(self, timeout=5.0):
        """Stop running code and wait for its thread, so closing never crashes."""
        self.interp.stop_requested = True
        self._input_value = None
        self._input_event.set()          # release a pending input() prompt
        deadline = time.time() + timeout
        for thread, _worker in list(getattr(self, "_threads", ())):
            try:
                while thread.isRunning() and time.time() < deadline:
                    QApplication.processEvents()   # delivers the queued quit()
                    thread.wait(20)
                if thread.isRunning():             # long NumPy call that cannot be interrupted
                    thread.terminate()
                    thread.wait(1000)
            except RuntimeError:                   # already deleted
                pass

    # -- running -------------------------------------------------------------
    def run_script(self):
        tab = self._tab()
        if tab is None:
            self.status_label.setText("Open or create a script first (Start page - New Script).")
            return
        code = tab.editor.toPlainText()
        if tab.path:
            self.interp.cwd = os.path.dirname(tab.path)
        tab.editor.set_error_line(None)
        name = os.path.basename(tab.path) if tab.path else tab.untitled
        self.console.echo(f"run {name}")
        self._start(code, tab)

    def run_selection(self):
        ed = self._editor()
        if not ed:
            return
        text = ed.textCursor().selectedText().replace(" ", "\n")
        if not text:
            text = ed.textCursor().block().text()
        self.run_command(text, echo=True)

    def run_command(self, code, echo=False):
        if self.running:
            self.status_label.setText("Busy — wait for the current run or press Stop.")
            return
        if echo:
            for line in code.splitlines() or [code]:
                self.console.echo(line)
        self._start(code, None)

    def _start(self, code, tab):
        if self.running:
            return
        self.running = True
        self.run_source = tab
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.console.set_busy(True)
        self.status_label.setText("Running...")
        thread = QThread(self)
        worker = RunWorker(self.interp, code)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._finished)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        # keep Python references alive until the thread has really stopped
        self._threads = getattr(self, "_threads", set())
        self._threads.add((thread, worker))
        thread.finished.connect(lambda t=thread, w=worker: self._threads.discard((t, w)))
        self.thread, self.worker = thread, worker
        thread.start()

    @Slot(object, float)
    def _finished(self, err, elapsed):
        self.running = False
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.console.set_busy(False)
        changed = self.interp.figures.finalize()
        self.figures.sync(self.interp.figures, changed)
        self.workspace.refresh(self.interp.base)
        if err is not None:
            self.console.write_error(str(err))
            self.status_label.setText(f"Error after {elapsed:.2f} s")
            if self.run_source is not None and err.line:
                self.editors.setCurrentWidget(self.run_source)
                self.run_source.editor.set_error_line(err.line)
        else:
            self.status_label.setText(f"Done in {elapsed:.2f} s")
        self.worker = None
        self.thread = None

    def stop(self):
        if self.running:
            self.interp.stop_requested = True
            self.status_label.setText("Stopping…")

    def _request_input(self, prompt):
        """Called from the worker thread by input(); blocks until the user answers."""
        self._input_event.clear()
        self.bridge.ask.emit(prompt)
        self._input_event.wait()
        return self._input_value

    @Slot(str)
    def _ask_input(self, prompt):
        text, ok = QInputDialog.getText(self, "Input", prompt or "Enter a value:")
        self._input_value = text if ok else None
        if ok:
            self.console.write(f"{prompt}{text}\n")
        self._input_event.set()

    # -- function browser ----------------------------------------------------
    def _filter_functions(self, text):
        text = text.lower().strip()
        for i in range(self.fn_list.count()):
            it = self.fn_list.item(i)
            data = it.data(Qt.ItemDataRole.UserRole)
            if data is None:
                it.setHidden(bool(text))
                continue
            name = data[0]
            tip = it.toolTip().lower()
            it.setHidden(bool(text) and text not in name.lower() and text not in tip)

    def _show_function(self, it, _prev=None):
        if it is None or it.data(Qt.ItemDataRole.UserRole) is None:
            return
        name = it.data(Qt.ItemDataRole.UserRole)[0]
        sig, en, ar, cat = HELP[name]
        self.fn_detail.setText(themed(f"<b style='color:#1565C0'>{sig}</b><br>{en}<br>"
                                      f"<div dir='rtl' style='color:#4A5B73'>{ar}</div>"))

    def _insert_function(self, it):
        data = it.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        name = data[0]
        ed = self._editor()
        if ed and ed.hasFocus():
            ed.insertPlainText(name + "(")
        else:
            self.console.input.setText(self.console.input.text() + name + "(")
            self.console.input.setFocus()

    def show_functions(self):
        self.left_tabs.setCurrentIndex(2)

    # -- tools ---------------------------------------------------------------
    def _open_tool(self, dlg):
        dlg.send_code.connect(self._code_from_tool)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.destroyed.connect(lambda *_: self.tools.remove(dlg) if dlg in self.tools else None)
        self.tools.append(dlg)
        dlg.show()

    def _code_from_tool(self, code):
        tab = self.new_tab(text=code)
        tab.editor.document().setModified(True)
        self.activateWindow()
        self.status_label.setText("Code inserted in a new script — press F5 to run it.")

    def open_pid(self):
        self._open_tool(PIDTuner(dict(self.interp.base), self))

    def open_routh(self):
        self._open_tool(RouthTool(self))

    def open_blocks(self):
        self._open_tool(BlockDiagramTool(self))

    def about(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("About HadaraLab")
        msg.setIconPixmap(QPixmap(asset("logo_256.png")).scaled(
            96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(themed(
            f"<h2 style='color:#1565C0; margin-bottom:2px'>HadaraLab {__version__}</h2>"
            "<div dir='rtl' style='font-size:10.5pt; line-height:150%'>"
            "برنامج <b>مفتوح المصدر</b> تابع إلى <b>كلية الحضارة الجامعة</b><br>"
            "<b>قسم هندسة تقنيات الحاسوب</b><br><br>"
            "برمجة وإعداد الطالب: <b>محمد عبدالرحمن محمود</b><br>"
            "الرخصة: <b>MIT</b> (رخصة مصادر مفتوحة)<br>"
            "الموقع الإلكتروني: <a href='https://mohmadev.com/'>mohmadev.com</a><br>"
            "البريد الإلكتروني للدعم: <a href='mailto:support@mohmadev.com'>support@mohmadev.com</a><br><br>"
            "<span style='color:#4A5B73'>لا يجمع البرنامج أي بيانات ولا يتصل بالإنترنت.<br>"
            "شعار الكلية واسمها ملكٌ لكلية الحضارة الجامعة، ويُستخدمان لهذا المشروع البرمجي فقط.</span>"
            "</div><hr>"
            "<div style='font-size:9.5pt; color:#4A5B73'>"
            "Open-source software of <b>Al-Hadara University College</b><br>"
            "Department of Computer Techniques Engineering<br>"
            "Developed by: <b>محمد عبدالرحمن محمود</b><br>"
            "License: MIT License (the college logo and name are excluded)<br>"
            "Website: <a href='https://mohmadev.com/'>https://mohmadev.com/</a><br>"
            "Support: <a href='mailto:support@mohmadev.com'>support@mohmadev.com</a>"
            "</div>"))
        privacy = msg.addButton("Privacy  -  الخصوصية", QMessageBox.ButtonRole.ActionRole)
        msg.addButton(QMessageBox.StandardButton.Ok)
        for lab in msg.findChildren(QLabel):
            lab.setOpenExternalLinks(True)
        msg.exec()
        if msg.clickedButton() is privacy:
            self.show_privacy()

    def show_privacy(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser
        dlg = QDialog(self)
        dlg.setWindowTitle("Privacy and notices  -  الخصوصية والإشعارات")
        dlg.resize(720, 640)
        lay = QVBoxLayout(dlg)
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        view.setHtml(themed(PRIVACY_HTML))
        lay.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        dlg.exec()
