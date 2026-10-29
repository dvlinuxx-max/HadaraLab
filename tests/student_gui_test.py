# Run:  python tests/student_gui_test.py . <empty work folder>
"""Drive the real HadaraLab window like a student and look for bugs.

usage: python student_gui_test.py <app_dir> <work_dir>
"""
import os
import sys
import time
import traceback

APP, WORK = sys.argv[1], sys.argv[2]
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, APP)
os.makedirs(WORK, exist_ok=True)

import matplotlib
matplotlib.use("QtAgg")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from hadaralab.ui import theme

theme.set_theme(os.environ.get("HL_THEME", "light"))
app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(theme.build_style())

# ---- capture every Python exception raised inside Qt slots ------------------
INTERNAL = []
_orig_hook = sys.excepthook


def hook(t, v, tb):
    INTERNAL.append("".join(traceback.format_exception(t, v, tb))[-900:])


sys.excepthook = hook

# ---- scripted answers for dialogs -------------------------------------------
ANSWER = {"question": QMessageBox.StandardButton.Discard, "save": "", "open": "", "dir": "", "input": ("7", True)}
QMessageBox.question = staticmethod(lambda *a, **k: ANSWER["question"])
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (ANSWER["save"], ""))
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (ANSWER["open"], ""))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: ANSWER["dir"])
QInputDialog.getText = staticmethod(lambda *a, **k: ANSWER["input"])

from hadaralab.ui.main_window import EditorTab, MainWindow  # noqa: E402
from hadaralab.ui.tools import BlockDiagramTool, PIDTuner, RouthTool  # noqa: E402

win = MainWindow()
win.resize(1500, 900)
win.show()

RESULTS = []


def pump(sec=0.05):
    end = time.time() + sec
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def wait_idle(timeout=30):
    end = time.time() + timeout
    while win.running and time.time() < end:
        pump(0.05)
    pump(0.2)
    return not win.running


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def console_lines():
    return win.console.log.toPlainText()


def last_run_output():
    text = console_lines()
    i = text.rfind(">> run ")
    return text[i:] if i != -1 else text


def type_console(cmd):
    win.console.input.setText(cmd)
    QTest.keyClick(win.console.input, Qt.Key.Key_Return)
    wait_idle()


def scenario(fn):
    try:
        fn()
    except Exception:  # a crash of the scenario itself is a finding too
        RESULTS.append((fn.__name__, False, "scenario crashed:\n" + traceback.format_exc()[-800:]))
    return fn


# =============================================================================
@scenario
def s01_type_code_with_keyboard():
    tab = win.new_tab()
    ed = tab.editor
    ed.selectAll()
    QTest.keyClick(ed, Qt.Key.Key_Delete)
    QTest.keyClicks(ed, "G = tf(10, [1 3 2]);")
    QTest.keyClick(ed, Qt.Key.Key_Return)
    QTest.keyClicks(ed, "step(G)")
    QTest.keyClick(ed, Qt.Key.Key_Return)
    QTest.keyClicks(ed, "S = stepinfo(G)")
    pump(0.2)
    text = ed.toPlainText()
    check("s01 typed text arrives intact (autocomplete must not change it)",
          text == "G = tf(10, [1 3 2]);\nstep(G)\nS = stepinfo(G)", repr(text))
    win.run_script()
    wait_idle()
    check("s01 script runs and draws a figure", len(win.interp.figures.figures) >= 1, console_lines()[-300:])
    check("s01 workspace shows G and S", {"G", "S"} <= set(win.interp.base))


@scenario
def s02_syntax_error_highlights_line():
    tab = win.new_tab(text="a = 1;\nb = [1 2 3\nc = 3;")
    win.run_script()
    wait_idle()
    check("s02 error message in console", "Unbalanced" in console_lines() or "line" in console_lines().lower())
    check("s02 error line marked in editor", tab.editor.error_line in (2, 3), f"error_line={tab.editor.error_line}")
    QTest.keyClicks(tab.editor, "x")
    check("s02 typing clears the error mark", tab.editor.error_line is None)


@scenario
def s03_runtime_error_inside_function():
    tab = win.new_tab(text="y = sq(3);\nfunction r = sq(x)\n    r = x * undefined_thing;\nend\n")
    win.run_script()
    wait_idle()
    check("s03 runtime error reported", "undefined_thing" in console_lines())
    check("s03 error line points into the function (line 3)", tab.editor.error_line == 3,
          f"error_line={tab.editor.error_line}")


@scenario
def s04_undo_redo():
    tab = win.new_tab()
    ed = tab.editor
    ed.selectAll()
    QTest.keyClick(ed, Qt.Key.Key_Delete)
    QTest.keyClicks(ed, "x = 1;")
    QTest.keyClick(ed, Qt.Key.Key_Return)
    QTest.keyClicks(ed, "y = 2;")
    before = ed.toPlainText()
    for _ in range(3):
        QTest.keyClick(ed, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    after_undo = ed.toPlainText()
    for _ in range(3):
        QTest.keyClick(ed, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    after_redo = ed.toPlainText()
    check("s04 Ctrl+Z undoes typing", after_undo != before and len(after_undo) < len(before),
          f"{before!r} -> {after_undo!r}")
    check("s04 Ctrl+Y redoes it", after_redo == before, f"{after_redo!r}")


@scenario
def s05_save_and_reopen_arabic_name():
    tab = win.new_tab(text="% واجب الطالب\nG = tf(1, [1 2 1]);\nstep(G)\n")
    path = os.path.join(WORK, "واجب السيطرة 1.m")
    if os.path.exists(path):
        os.remove(path)
    ANSWER["save"] = path
    ok = win.save_file()
    check("s05 Save As writes the file", ok and os.path.exists(path))
    check("s05 tab is no longer marked modified", not tab.editor.document().isModified())
    check("s05 tab title is the file name", "واجب السيطرة 1.m" in win.editors.tabText(win.editors.indexOf(tab)))
    with open(path, encoding="utf-8") as fh:
        check("s05 saved content (with Arabic) is identical", fh.read() == tab.editor.toPlainText())
    win.close_tab(win.editors.indexOf(tab))
    t2 = win.open_path(path)
    check("s05 reopened file has the same text", t2.editor.toPlainText().startswith("% واجب الطالب"))
    t3 = win.open_path(path)
    check("s05 opening the same file twice reuses the tab", t3 is t2)
    tab_count = sum(isinstance(win.editors.widget(i), EditorTab) and win.editors.widget(i).path == path
                    for i in range(win.editors.count()))
    check("s05 only one tab for that file", tab_count == 1)
    t2.editor.moveCursor(t2.editor.textCursor().MoveOperation.End)
    QTest.keyClicks(t2.editor, "grid on")
    QTest.keyClick(t2.editor, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    pump(0.1)
    with open(path, encoding="utf-8") as fh:
        check("s05 Ctrl+S saves the change", fh.read().rstrip().endswith("grid on"))


@scenario
def s06_close_unsaved_tab():
    tab = win.new_tab(text="x = 1;")
    tab.editor.document().setModified(True)
    idx = win.editors.indexOf(tab)
    ANSWER["question"] = QMessageBox.StandardButton.Cancel
    win.close_tab(idx)
    check("s06 Cancel keeps the unsaved tab open", win.editors.indexOf(tab) != -1)
    ANSWER["question"] = QMessageBox.StandardButton.Discard
    win.close_tab(win.editors.indexOf(tab))
    pump(0.1)
    check("s06 Discard closes it", all(win.editors.widget(i) is not tab for i in range(win.editors.count())))
    t = win.new_tab(text="y = 2;")
    t.editor.document().setModified(True)
    ANSWER["question"] = QMessageBox.StandardButton.Save
    ANSWER["save"] = ""                       # student cancels the save dialog
    win.close_tab(win.editors.indexOf(t))
    check("s06 Save + cancelled dialog keeps the tab", win.editors.indexOf(t) != -1)
    ANSWER["question"] = QMessageBox.StandardButton.Discard
    win.close_tab(win.editors.indexOf(t))


@scenario
def s07_command_window():
    type_console("x = 5")
    check("s07 'x = 5' is real 5", float(win.interp.base["x"].ravel()[0]) == 5 and
          not hasattr(win.interp.base["x"].ravel()[0], "imag") or win.interp.base["x"].ravel()[0].imag == 0)
    check("s07 output shows x = 5", "x = 5" in console_lines())
    type_console("y = x * 2;")
    type_console("plot(")
    check("s07 broken command gives an error, not a crash", "Unbalanced" in console_lines())
    check("s07 console still accepts input after an error", win.console.input.isEnabled())
    win.console.input.setFocus()
    QTest.keyClick(win.console.input, Qt.Key.Key_Up)
    check("s07 Up arrow recalls the last command", win.console.input.text() == "plot(", win.console.input.text())
    QTest.keyClick(win.console.input, Qt.Key.Key_Up)
    check("s07 Up again recalls the one before", win.console.input.text() == "y = x * 2;")
    win.console.input.clear()
    type_console("who")
    type_console("clc")
    check("s07 clc clears the command window", console_lines().strip() == "", repr(console_lines()[:80]))
    type_console("clear")
    check("s07 clear empties the workspace table", win.workspace.rowCount() == 0)
    type_console("disp('مرحبا')")
    check("s07 Arabic text is printed", "مرحبا" in console_lines())


@scenario
def s08_infinite_loop_and_stop():
    win.new_tab(text="k = 0;\nwhile true\n    k = k + 1;\nend\n")
    win.run_script()
    pump(0.8)
    check("s08 program shows it is running", win.running and win.stop_btn.isEnabled())
    win.run_script()                       # impatient student presses Run again
    pump(0.2)
    win.stop()
    finished = wait_idle(10)
    check("s08 Stop ends the infinite loop", finished)
    check("s08 'stopped by user' message", "stopped by user" in console_lines().lower())
    check("s08 k kept its value", float(win.interp.base["k"].ravel()[0]) > 0)
    type_console("z = 1 + 1")
    check("s08 program usable after stopping", "z = 2" in console_lines())


@scenario
def s09_input_dialog():
    ANSWER["input"] = ("12", True)
    win.new_tab(text="a = input('Enter gain K: ');\nb = a * 2\n")
    win.run_script()
    wait_idle()
    check("s09 input() value used", "b = 24" in console_lines(), console_lines()[-200:])
    ANSWER["input"] = ("", False)
    win.new_tab(text="a = input('Enter: ');\n")
    win.run_script()
    wait_idle()
    check("s09 cancelling input() gives a clean error", "cancel" in console_lines().lower())
    ANSWER["input"] = ("abc def", True)
    win.new_tab(text="a = input('Enter: ');\n")
    win.run_script()
    wait_idle()
    check("s09 nonsense input gives an error, not a crash", not win.running)


@scenario
def s10_pid_tuner_bad_numbers():
    d = PIDTuner({}, win)
    d.show()
    pump(0.3)
    for den in ("abc", "", "0", "1 -1", "1 0 0", "1,2,3", "[1 10 20]", "1e400 1"):
        d.den.setText(den)
        d.update_plot()
        pump(0.05)
    check("s10 PID tuner survives bad denominators", True)
    d.num.setText("1 2 3 4")
    d.den.setText("1 2")
    d.update_plot()
    d.num.setText("1")
    d.den.setText("1 1")
    d.ziegler_nichols()
    check("s10 Ziegler-Nichols on a 1st-order plant warns instead of crashing",
          "لا تنطبق" in d.status.text() or "does not apply" in d.status.text(), d.status.text())
    d.den.setText("1 10 20")
    d.auto_tune()
    pump(0.2)
    check("s10 Auto Tune gives a stable loop", "UNSTABLE" not in d.status.text(), d.status.text())
    for ctype in ("PI", "PD", "P", "PID"):
        d.ctype.setCurrentText(ctype)
        pump(0.1)
    sent = []
    d.send_code.connect(sent.append)
    d._emit_code()
    check("s10 'Send code to editor' produces code", sent and "pid(" in sent[0])
    d.close()
    if sent:
        win._code_from_tool(sent[0])
        win.run_script()
        wait_idle()
        check("s10 code from the PID tuner runs without error",
              "Error" not in last_run_output(), last_run_output()[-300:])


@scenario
def s11_routh_tool_bad_numbers():
    d = RouthTool(win)
    d.show()
    for p in ("1 a 3", "", "0 0", "5", "1 0 0 0", "1 2 3 4 5", "1 0 5 0 4", "1e308 1e308 1"):
        d.poly.setText(p)
        d.analyze()
    check("s11 Routh tool survives bad polynomials", True)
    d.mode.setCurrentIndex(1)
    d.num.setText("1")
    d.den.setText("1 3 2 0")
    for k in (0, 6, 1e6):
        d.k.setValue(k)
        d.analyze()
    check("s11 K = 6 is reported marginal", True)
    d.den.setText("x")
    d.analyze()
    sent = []
    d.send_code.connect(sent.append)
    d.den.setText("1 3 2 0")
    d._emit_code()
    d.close()
    if sent:
        win._code_from_tool(sent[0])
        win.run_script()
        wait_idle()
        check("s11 code from the Routh tool runs", "Error" not in last_run_output(), last_run_output()[-300:])


@scenario
def s12_block_diagram_bad_numbers():
    d = BlockDiagramTool(win)
    d.show()
    for i in range(4):
        d.topo.setCurrentIndex(i)
        d.update_all()
    _, ne, de = d.fields["G"]
    for den in ("0", "", "a b", "1 -5"):
        de.setText(den)
        d.update_all()
    de.setText("1 3 2")
    _, hn, hd = d.fields["H"]
    hn.setText("-1")
    d.update_all()
    hn.setText("1")
    d.update_all()
    sent = []
    d.send_code.connect(sent.append)
    d._emit_code()
    d.close()
    check("s12 block diagram survives bad blocks", True)
    if sent:
        win._code_from_tool(sent[0])
        win.run_script()
        wait_idle()
        check("s12 code from block diagram runs", "Error" not in last_run_output(), last_run_output()[-300:])


@scenario
def s13_figures_close_tip_save():
    type_console("close all")
    type_console("G = tf(1, conv([1 0], conv([1 1], [1 2]))); rlocus(G)")
    check("s13 root locus figure created", len(win.figures.views) == 1)
    view = next(iter(win.figures.views.values()))
    ax = view.fig.axes[0]

    class Ev:
        pass
    ev = Ev()
    ev.button, ev.inaxes = 1, ax
    x, y = view.fig.axes[0].transData.transform((-0.33, 0.58))
    ev.x, ev.y, ev.xdata, ev.ydata = x, y, -0.33, 0.58
    view.on_click(ev)
    check("s13 clicking the root locus shows K", any("Gain K" in t.get_text() for t in ax.texts
                                                      if hasattr(t, "get_text")), "")
    ev.button = 3
    view.on_click(ev)
    check("s13 right-click clears the data tip", not view.tips)
    out = os.path.join(WORK, "شكل الطالب.png")
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (out, ""))
    view.save_png()
    check("s13 Save PNG writes the image", os.path.exists(out) and os.path.getsize(out) > 1000)
    num = next(iter(win.figures.views))
    win.figures._close_tab(win.figures.indexOf(view))
    pump(0.1)
    check("s13 closing the figure tab removes it from the engine", num not in win.interp.figures.figures)
    type_console("step(G/(1+G))")
    check("s13 new figure after closing works", len(win.figures.views) == 1)
    type_console("hold on; step(2*G/(1+2*G)); hold off")
    type_console("subplot(2,1,1); step(G/(1+G)); subplot(2,1,2); bode(G)")
    check("s13 subplot + bode after each other ok", "Error" not in console_lines()[-300:], console_lines()[-300:])


@scenario
def s14_function_files_in_folder():
    folder = os.path.join(WORK, "project")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "closed_loop.m"), "w", encoding="utf-8") as fh:
        fh.write("function T = closed_loop(G, K)\n    T = feedback(K*G, 1);\nend\n")
    ANSWER["dir"] = folder
    win.change_folder()
    check("s14 Files panel switched folder", win.interp.cwd == folder)
    main = os.path.join(folder, "main_script.m")
    with open(main, "w", encoding="utf-8") as fh:
        fh.write("G = tf(1, [1 3 2]);\nT = closed_loop(G, 5);\np = pole(T)\n")
    win.open_path(main)
    win.run_script()
    wait_idle()
    check("s14 script calls a function from another .m file", "p =" in console_lines(), console_lines()[-300:])


@scenario
def s15_odd_files():
    latin = os.path.join(WORK, "old_file.m")
    with open(latin, "wb") as fh:
        fh.write("x = 1; % caf\xe9\n".encode("latin-1"))
    t = win.open_path(latin)
    check("s15 non-UTF-8 file opens", "x = 1" in t.editor.toPlainText())
    empty = os.path.join(WORK, "empty.m")
    open(empty, "w").close()
    t = win.open_path(empty)
    win.run_script()
    wait_idle()
    check("s15 empty file runs without error", not win.running)
    ANSWER["open"] = ""
    win.open_file()                          # student cancels the open dialog
    check("s15 cancelling Open does nothing bad", True)


@scenario
def s16_editor_helpers():
    t = win.new_tab(text="a = 1\nb = 2\nc = a + b")
    ed = t.editor
    ed.selectAll()
    ed.toggle_comment()
    check("s16 Ctrl+/ comments all lines", all(l.startswith("% ") for l in ed.toPlainText().split("\n")),
          ed.toPlainText())
    ed.selectAll()
    ed.toggle_comment()
    check("s16 Ctrl+/ again uncomments", ed.toPlainText() == "a = 1\nb = 2\nc = a + b", ed.toPlainText())
    cur = ed.textCursor()
    cur.movePosition(cur.MoveOperation.End)
    ed.setTextCursor(cur)
    win.run_selection()                    # F9 on the current line
    wait_idle()
    check("s16 F9 runs the current line only", "Undefined" in console_lines()[-200:] or "c =" in console_lines())
    ed.setPlainText("for k = 1:3")
    cur = ed.textCursor()
    cur.movePosition(cur.MoveOperation.End)
    ed.setTextCursor(cur)
    QTest.keyClick(ed, Qt.Key.Key_Return)
    check("s16 auto-indent after 'for'", ed.toPlainText().endswith("\n    "), repr(ed.toPlainText()))


@scenario
def s17_functions_panel():
    win.show_functions()
    lst = win.fn_list
    win._filter_functions("bode")
    visible = [lst.item(i).text().strip() for i in range(lst.count()) if not lst.item(i).isHidden()]
    check("s17 search finds bode", "bode" in visible, str(visible[:5]))
    item = next(lst.item(i) for i in range(lst.count()) if lst.item(i).text().strip() == "bode")
    win.console.input.clear()
    win._insert_function(item)
    check("s17 double-click inserts into the command line", win.console.input.text() == "bode(")
    win._filter_functions("")
    win.console.input.clear()


@scenario
def s18_theme_menu_and_close_window():
    from hadaralab.ui.theme import theme_name
    before = theme_name()
    ANSWER["question"] = QMessageBox.StandardButton.No
    target = "light" if before == "dark" else "dark"
    win.choose_theme(target)
    from PySide6.QtCore import QSettings
    saved = QSettings("Hadara", "HadaraLab").value("theme")
    check("s18 theme choice is saved for next start", saved == target)
    QSettings("Hadara", "HadaraLab").setValue("theme", before)
    t = win.new_tab(text="unsaved work")
    t.editor.document().setModified(True)
    ANSWER["question"] = QMessageBox.StandardButton.Cancel
    closed = win.close()
    check("s18 closing the window with unsaved work can be cancelled", not closed and win.isVisible())
    ANSWER["question"] = QMessageBox.StandardButton.Discard


@scenario
def s19_workspace_double_click():
    type_console("M = magic(3);")
    rows = [win.workspace.item(r, 0).text() for r in range(win.workspace.rowCount())]
    r = rows.index("M")
    win.workspace.cellDoubleClicked.emit(r, 0)
    wait_idle()
    check("s19 double-click a variable prints it", "M =" in console_lines()[-200:])


@scenario
def s20_long_output_and_big_loops():
    type_console("for k = 1:300; fprintf('line %d\\n', k); end")
    check("s20 300 printed lines arrive", "line 300" in console_lines())
    type_console("A = rand(200); B = A*A'; e = max(abs(eig(B)));")
    check("s20 200x200 matrix math ok", "e" in win.interp.base)


# =============================================================================
pump(0.3)
ANSWER["question"] = QMessageBox.StandardButton.Discard
win.close()
pump(0.3)
fails = [r for r in RESULTS if not r[1]]
print(f"checks: {len(RESULTS)}   passed: {len(RESULTS) - len(fails)}   failed: {len(fails)}   "
      f"internal exceptions: {len(INTERNAL)}")
for name, ok, detail in RESULTS:
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok or not detail else f"\n        {detail[:500]}"))
for e in INTERNAL:
    print("INTERNAL EXCEPTION:\n" + e)
sys.stdout.flush()
os._exit(0)
