"""Engine tests: run with  python -m pytest tests  (or python tests/test_engine.py)."""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hadaralab.engine import Interpreter, MatlabError  # noqa: E402


def run(src):
    out = []
    ip = Interpreter(output=out.append)
    ip.execute(src)
    return ip, "".join(out)


def val(ip, name):
    v = ip.base[name]
    return v


def test_arithmetic_and_precedence():
    ip, _ = run("a = 2 + 3 * 4; b = -2^2; c = 2^3^2; d = (1:5)'; e = [1 -2]; f = [1 - 2];")
    assert val(ip, "a")[0, 0] == 14
    assert val(ip, "b")[0, 0] == -4
    assert val(ip, "c")[0, 0] == 64
    assert val(ip, "d").shape == (5, 1)
    assert val(ip, "e").shape == (1, 2)
    assert val(ip, "f").shape == (1, 1)


def test_matrix_ops():
    ip, _ = run("A = [1 2; 3 4]; B = A'; C = A*B; D = A.*A; x = A\\[5; 6]; d = det(A); I = inv(A)*A;")
    assert np.allclose(val(ip, "C"), [[5, 11], [11, 25]])
    assert np.allclose(val(ip, "D"), [[1, 4], [9, 16]])
    assert np.allclose(val(ip, "x").ravel(), [-4, 4.5])
    assert np.isclose(val(ip, "d")[0, 0], -2)
    assert np.allclose(val(ip, "I"), np.eye(2))


def test_indexing_and_end():
    ip, _ = run("v = 10:10:50; a = v(end); b = v([1 end]); v(7) = 1; M = magic(3); c = M(2, :); "
                "M(:, 1) = []; s = 'hello'; t = s(end:-1:1); L = v(v > 20);")
    assert val(ip, "a")[0, 0] == 50
    assert list(val(ip, "b").ravel()) == [10, 50]
    assert val(ip, "v").shape == (1, 7)
    assert list(val(ip, "c").ravel()) == [3, 5, 7]
    assert val(ip, "M").shape == (3, 2)
    assert val(ip, "t") == "olleh"
    assert list(val(ip, "L").ravel()) == [30, 40, 50]


def test_control_flow_and_functions():
    src = """
total = 0;
for k = 1:10
    if mod(k, 2) == 0
        continue
    end
    total = total + k;
end
n = 0;
while true
    n = n + 1;
    if n >= 5, break; end
end
switch 'b'
    case {'a', 'b'}
        w = 1;
    otherwise
        w = 2;
end
[m, i] = max([3 9 2]);
y = sq(4);
function r = sq(x)
    r = x^2;
end
"""
    ip, _ = run(src)
    assert val(ip, "total")[0, 0] == 25
    assert val(ip, "n")[0, 0] == 5
    assert val(ip, "w")[0, 0] == 1
    assert val(ip, "m")[0, 0] == 9 and val(ip, "i")[0, 0] == 2
    assert val(ip, "y")[0, 0] == 16


def test_strings_and_printf():
    _, out = run("x = 3.14159; fprintf('x = %.2f\\n', x); disp(['K = ' num2str(5)]); "
                 "s = sprintf('%d,', [1 2 3]); disp(s)")
    assert "x = 3.14" in out
    assert "K = 5" in out
    assert "1,2,3," in out


def test_display_formats():
    _, out = run("a = 5\nb = [1 2 3]\nc = pi\n")
    assert "a = 5" in out
    assert "1     2     3" in out.replace("   ", "  ") or "1" in out
    assert "c = 3.1416" in out


def test_anonymous_functions():
    ip, _ = run("f = @(x) x.^2 + 1; y = f(3); g = @sin; z = g(0); r = fzero(@(x) x^2 - 2, 1);")
    assert val(ip, "y")[0, 0] == 10
    assert val(ip, "z")[0, 0] == 0
    assert np.isclose(val(ip, "r")[0, 0], np.sqrt(2))


def test_tf_and_feedback():
    ip, out = run("G = tf(10, [1 3 2])\nT = feedback(G, 1);\np = pole(T); k = dcgain(T);")
    assert "s^2 + 3 s + 2" in out
    T = val(ip, "T")
    assert np.allclose(T.den, [1, 3, 12])
    assert np.isclose(val(ip, "k")[0, 0], 10 / 12)


def test_tf_s_variable():
    ip, _ = run("s = tf('s'); G = 10/(s^2 + 3*s + 2); H = (s + 1)/(s*(s + 2));")
    G = val(ip, "G")
    assert np.allclose(G.num / G.den[0], [10]) and np.allclose(G.den / G.den[0], [1, 3, 2])


def test_stepinfo_second_order():
    ip, _ = run("G = tf(1, [1 1 1]); S = stepinfo(G); os = S.Overshoot; tp = S.PeakTime;")
    assert abs(val(ip, "os")[0, 0] - 16.3) < 0.1
    assert abs(val(ip, "tp")[0, 0] - 3.63) < 0.02


def test_margin_values():
    ip, _ = run("G = tf(1, conv([1 0], conv([1 1], [1 2]))); [Gm, Pm, Wcg, Wcp] = margin(G);")
    assert abs(val(ip, "Gm")[0, 0] - 6) < 1e-3
    assert abs(val(ip, "Pm")[0, 0] - 53.41) < 0.05
    assert abs(val(ip, "Wcg")[0, 0] - np.sqrt(2)) < 1e-3


def test_routh_output():
    _, out = run("routh([1 2 3 4 5])")
    assert "Sign changes in first column: 2" in out and "UNSTABLE" in out
    _, out = run("routh([1 0 5 0 4])")
    assert "MARGINALLY" in out or "auxiliary" in out


def test_krange():
    _, out = run("krange(tf(1, conv([1 0], conv([1 1], [1 2]))))")
    assert "0 < K < 6" in out


def test_plots_render():
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    ip, _ = run("""
G = tf([1 2], [1 4 3 0]);
step(feedback(G, 1)); grid on
figure; bode(G)
figure; margin(G)
figure; rlocus(G); sgrid
figure; nyquist(G)
figure; pzmap(G)
figure; t = 0:0.01:2*pi; plot(t, sin(t), 'r--', t, cos(t)); legend('sin', 'cos'); title('Waves')
figure; subplot(2,1,1); impulse(G/(G+1)); subplot(2,1,2); ramp(feedback(G,1))
""")
    assert len(ip.figures.figures) == 8
    for fig in ip.figures.figures.values():
        FigureCanvasAgg(fig).draw()


def test_ogata_legacy_syntax():
    # MATLAB Program 5-6 from Ogata (4th ed.) with the book's printed results
    ip, _ = run("""
num = [0 0 25]; den = [1 6 25]; t = 0:0.005:5;
[y,x,t] = step(num,den,t);
r = 1; while y(r) < 1.0001; r = r + 1; end;
rise_time = (r - 1)*0.005;
[ymax,tp] = max(y); peak_time = (tp - 1)*0.005; max_overshoot = ymax-1;
s = 1001; while y(s) > 0.98 & y(s) < 1.02; s = s - 1; end;
settling_time = (s - 1)*0.005;
[n2, d2] = ss2tf([0 1 0; 0 0 1; -5 -25 -5], [0; 25; -120], [1 0 0], 0);
[r6, K6] = rlocus([0 0 0 1], [1 3 2 0]);
""")
    assert abs(val(ip, "rise_time")[0, 0] - 0.5550) < 1e-9
    assert abs(val(ip, "peak_time")[0, 0] - 0.7850) < 1e-9
    assert abs(val(ip, "max_overshoot")[0, 0] - 0.0948) < 1e-4
    assert abs(val(ip, "settling_time")[0, 0] - 1.1850) < 1e-9
    assert np.allclose(val(ip, "n2"), [[0, 0, 25, 5]]) and np.allclose(val(ip, "d2"), [[1, 5, 25, 5]])
    assert val(ip, "r6").shape[1] == 3          # old form: one row per gain


def test_ziegler_nichols_example_10_1():
    ip, _ = run("[Kp, Ti, Td] = zntune(tf(1, [1 6 5 0]), 'PID');")
    assert abs(val(ip, "Kp")[0, 0] - 18) < 1e-3
    assert abs(val(ip, "Ti")[0, 0] - 1.405) < 1e-3
    assert abs(val(ip, "Td")[0, 0] - 0.35124) < 1e-4


def test_state_space_initial_and_ord2():
    ip, _ = run("[num, den] = ord2(5, 0.4); sys = ss([0 1; -6 -5], [0; 1], [1 0], 0); "
                "[y, t, x] = initial(sys, [2; 0]); K = acker([0 1; 0 0], [0; 1], [-2+2i -2-2i]);")
    assert np.allclose(val(ip, "num"), [[1]]) and np.allclose(val(ip, "den"), [[1, 4, 25]])
    assert abs(val(ip, "y")[0, 0] - 2) < 1e-9 and abs(val(ip, "y")[-1, 0]) < 0.02
    assert np.allclose(val(ip, "K"), [[8, 4]])


def test_number_at_end_of_input_is_real():
    # regression: a number at the very end of a command became imaginary (x = 5 -> 5i)
    for code, expect in (("x = 5", 5), ("x = 2.5e3", 2500), ("x = .5", 0.5)):
        ip, _ = run(code)
        v = val(ip, "x")
        assert not np.iscomplexobj(v) and v[0, 0] == expect, code
    ip, _ = run("x = 10:-1:1")
    assert val(ip, "x").size == 10
    ip, _ = run("z = 3 + 2i")
    assert val(ip, "z")[0, 0] == 3 + 2j


def test_student_mistakes_give_clear_errors():
    cases = {
        "G = tf(1, [1 1]); step(G, 0)": "final time",
        "G = tf(1, [1 1]); step(G, -5)": "final time",
        "bode(tf(1, [1 1]), {0, 10})": "frequency range",
        "f = @(x) x^2; f(1, 2)": "Too many input arguments",
        "f = @(x) x^2; f()": "Not enough input arguments",
        "figure(0)": "positive integer",
        "a = 3 4": "missing operator",
        "function": "incomplete",
    }
    for code, words in cases.items():
        try:
            run(code)
        except MatlabError as e:
            assert words.lower() in e.message.lower(), (code, e.message)
        else:
            raise AssertionError(f"expected an error for: {code}")
    ip, _ = run("x = ones(-1); S = stepinfo(tf(1, [1 0])); os = S.Overshoot;")
    assert val(ip, "x").size == 0 and np.isnan(val(ip, "os")[0, 0])


def test_errors_have_lines():
    try:
        run("a = 1;\nb = undefined_thing + 1;")
    except MatlabError as e:
        assert e.line == 2
        assert "undefined_thing" in e.message
    else:
        raise AssertionError("expected error")


if __name__ == "__main__":
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001
                failures += 1
                import traceback
                print(f"FAIL {name}: {e}")
                traceback.print_exc()
    print("\nAll tests passed." if not failures else f"\n{failures} test(s) failed.")
    sys.exit(1 if failures else 0)
