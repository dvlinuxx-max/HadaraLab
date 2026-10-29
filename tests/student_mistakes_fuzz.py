# Run:  python tests/student_mistakes_fuzz.py .
"""Student-mistake fuzz test for the HadaraLab engine.

Every snippet must either run, or fail with a clear MATLAB-style error.
Python-internal messages, crashes and hangs are reported as BUGS.
"""
import os
import re
import sys
import threading
import time

APP = sys.argv[1]
sys.path.insert(0, APP)
import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402
from hadaralab.engine import Interpreter, MatlabError  # noqa: E402

CASES = [
    # --- syntax mistakes -----------------------------------------------------
    "x = [1 2 3",            "x = (1 + 2",            "x = 1 +",              "y = = 2",
    "for k = 1:3 disp(k)",   "if x > 1",              "end",                  "function",
    "x = 'hello",            "x = \"hi",              "a = 3 4",              "a = [1 2; 3]",
    "a = [1, , 2]",          "x = 1;;; y = 2",        "1 = x",                "x(1 = 2",
    "tf(1, [1 2 3]",         "step(G",                "x = 5 % comment )",    "x = [1 2]'';",
    "x = 2^",                "x = .5 + .",            "x = 1e",               "x = 3..4",
    "x = @",                 "f = @(x x+1",           "x = {1, 2",            "x.y.z = ",
    "while", "switch x", "case 1", "else", "elseif 1", "x = $5", "x = 5 &", "x = ~",
    # --- runtime mistakes ----------------------------------------------------
    "y = undefined_var + 1", "x = [1 2 3]; x(0)",     "x = [1 2 3]; x(4)",    "x = [1 2 3]; x(1.5)",
    "x = [1 2 3]; x(-1)",    "A = [1 2; 3 4]; B = [1 2 3]; A*B", "A = ones(2,3) + ones(3,2)",
    "A = [1 2; 3 4]; A^0.5", "inv([1 2; 2 4])",       "det([1 2 3])",          "x = 1/0",
    "x = 0/0",               "x = log(0)",            "x = sqrt(-4)",          "x = 'abc' + 1",
    "x = 'abc' * [1 2]",     "s.a = 1; s.b",          "s = 5; s.a = 1",        "x = 5; x{1}",
    "c = {1,2}; c + 1",      "x = []; x(3) = 5",      "x = zeros(2); x(3,3) = 1", "x = 1:0",
    "x = 10:-1:1", "x = 1:0.1:2", "x = linspace(0,1,0)", "x = ones(-1)", "x = zeros(2,3)'",
    "max([])", "min([])", "sum([])", "mean([])", "x = [1 2; 3 4]; x(:)'", "x = magic(4); x(end, end)",
    "x = 5; x(2)", "x = 'abc'; x(5)", "y = sin()", "y = sin(1, 2)", "y = plot()",
    "y = zeros('a')", "num2str()", "fprintf()", "fprintf('%d %d\\n', 1)", "sprintf('%s', 5)",
    "disp()", "x = input('?')", "error('my error %d', 5)", "a = b = 3", "pi = 3; area = pi*2^2",
    "i = 5; z = 3 + 2i", "e = exp(1)", "x = true + true", "x = ~[1 0 2]",
    "for k = []; disp(k); end", "for k = 'abc'; disp(k); end", "k = 0; while k < 3; k = k + 1; end",
    "x = 1; x(2,:) = [1 2]", "f = @(x) x^2; f(1, 2)", "f = @(x) x^2; f()", "f = 5; f(1)(2)",
    "x = 1; clear x; x", "clear all; who", "format long; pi", "format bad",
    "x = rand(3); x(4, 4)", "x = 'عربي'; disp(x)", "disp('مرحبا بالعالم')",
    # --- control-system mistakes ---------------------------------------------
    "G = tf()", "G = tf(1)", "G = tf(1, 0)", "G = tf(1, [0 0])", "G = tf([], [1 2])",
    "G = tf('abc')", "G = tf([1 2 3 4], [1 2]); step(G)", "G = tf([1 2], [1 2]); step(G)",
    "G = tf(1, [1 -1]); step(G)", "G = tf(1, [1 0 1]); step(G)", "G = tf(1, [1 0 0]); step(G)",
    "G = tf(1, [1 2 1]); step(G, -5)", "G = tf(1, [1 2 1]); step(G, 0)", "step(5)", "step('G')",
    "step()", "bode()", "G = tf(1,[1 1]); bode(G, 'r', 'x')", "G = tf(1, [1 1]); rlocus(G)",
    "G = tf(1, [1 1 0]); margin(G)", "G = tf(0, [1 1]); rlocus(G)", "G = tf(0, [1 1]); margin(G)",
    "G = tf(1, [1 1]); nyquist(G)", "G = tf(1, [1 0]); nyquist(G)", "G = tf(1, [1 0 0]); bode(G)",
    "routh([])", "routh(0)", "routh([0 0 1])", "routh([1])", "routh([1 0 0 0])", "routh('abc')",
    "routh([1 2 3 4 5 6 7 8 9 10])", "krange(tf(1, [1 1]))", "krange(tf([1 1], [1 2 3]))",
    "zntune(tf(1, [1 1]))", "zntune(tf(1, [1 1 0]), 'PIDD')", "pid()", "pid('a')",
    "feedback()", "feedback(tf(1,[1 1]), tf(-1, 1))", "feedback(tf(1,[1 1]), tf(1, 1), 1)",
    "G = tf(1, [1 1]); G(2)", "G = tf(1,[1 1]); G + [1 2]", "G = tf(1,[1 1]); G ^ 0.5",
    "G = tf(1,[1 1]); G / 0", "G = tf(1,[1 1]); [G G]", "s = tf('s'); G = 1/s^2; step(G)",
    "s = tf('s'); G = s; step(G)", "stepinfo(tf(1, [1 -2]))", "stepinfo(tf(1, [1 0]))",
    "stepinfo([1 2 3])", "ess(tf(1, [1 1]))", "ess(5)", "damp(tf(1, [1 0]))",
    "pzmap(tf(1, [1 2 2]))", "ss([1 2], 1, 1, 0)", "ss(1, 1, 1)", "initial(tf(1,[1 1]), 1)",
    "initial(ss([0 1; -1 -1], [0;1], [1 0], 0), [1 2 3])", "lsim(tf(1,[1 1]), [1 2], 0:0.1:1)",
    "rlocfind(tf(1, [1 3 2 0]), -0.5)", "rlocfind(tf(1,[1 1]), -1)",
    "acker([0 1; 0 0], [1; 0], [-1 -2])", "lqr([0 1;0 0],[0;1],eye(3),1)",
    "minreal(tf([1 1], [1 1]))", "zpk([], [], 0)", "ord2(-1, 0.5)", "stepspecs(1.5, 2)",
    "G = tf(1, [1 3 2]); step(G, 1:0)", "bode(tf(1,[1 1]), {0, 10})", "sgrid",
    "subplot(2,2,5)", "subplot(0,0,0)", "axis([1 0 0 1])", "xlim([1 1])", "legend()",
    "plot([1 2 3], [1 2])", "plot('abc')", "plot([])", "figure(0)", "figure(-1)", "close(99)",
    "hold", "grid", "mesh([1 2 3])", "polar([0 1], [1])", "title(5)", "gtext()",
    # --- loops a student might write ------------------------------------------
    "for i = 1:100000; x(i) = i^2; end",
    "s = 0; for k = 1:1000; s = s + 1/k^2; end; s",
    "n = 0; while n < 1e5; n = n + 1; end",
]

BAD_PATTERNS = [
    "Internal error", "Traceback", "object has no attribute", "NoneType", "list index",
    "tuple index", "unsupported operand", "not subscriptable", "unhashable", "invalid literal",
    "can't multiply sequence", "ufunc", "numpy", "operands could not be broadcast",
    "only integer scalar arrays", "takes from", "positional argument", "keyword argument",
    "is not iterable", "math domain", "too many values to unpack", "not enough values",
    "zero-size array", "axis 1 is out of bounds", "invalid index", "has no len",
    "object is not callable", "'float' object", "'int' object", "'str' object",
    "Cannot convert", "TypeError", "ValueError", "KeyError", "IndexError", "AttributeError",
]

report = {"ok": 0, "matlab_error": 0, "bugs": []}
start = time.time()
for code in CASES:
    out = []
    ip = Interpreter(output=out.append)
    ip.on_input = lambda prompt: "7"
    res = {}

    def run():
        try:
            ip.execute(code)
            for fig in ip.figures.figures.values():
                FigureCanvasAgg(fig).draw()
            res["status"] = "ok"
        except MatlabError as e:
            res["status"] = "err"
            res["msg"] = str(e)
        except BaseException as e:  # noqa: BLE001 - this is exactly what we hunt for
            res["status"] = "crash"
            res["msg"] = f"{type(e).__name__}: {e}"

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(20)
    if th.is_alive():
        ip.stop_requested = True
        th.join(3)
        report["bugs"].append((code, "HANG (no answer after 20 s)"))
        continue
    st = res.get("status")
    if st == "ok":
        report["ok"] += 1
        text = "".join(out)
        if any(p in text for p in ("Traceback", "Internal error")):
            report["bugs"].append((code, "output contains internal error: " + text[:200]))
    elif st == "err":
        msg = res["msg"]
        if any(p.lower() in msg.lower() for p in BAD_PATTERNS) or len(msg) < 12:
            report["bugs"].append((code, "unclear message -> " + msg[:220]))
        else:
            report["matlab_error"] += 1
    else:
        report["bugs"].append((code, "CRASH -> " + res.get("msg", "?")[:220]))

print(f"cases: {len(CASES)}   ran OK: {report['ok']}   clear MATLAB errors: {report['matlab_error']}   "
      f"bugs: {len(report['bugs'])}   ({time.time() - start:.1f} s)")
for code, why in report["bugs"]:
    print(f"  BUG  {code!r}\n       {why}")
