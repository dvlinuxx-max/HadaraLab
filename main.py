"""HadaraLab - start the application.

    python main.py
"""

import os
import sys

if sys.platform == "win32":
    try:  # give the app its own taskbar icon instead of python.exe's
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Hadara.HadaraLab.1")
    except Exception:
        pass

import matplotlib

matplotlib.use("QtAgg")

from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from hadaralab import __version__
from hadaralab.ui.theme import asset, build_style, is_dark, load_saved_theme


def make_splash():
    w, h = 620, 340
    pm = QPixmap(w, h)
    pm.fill(QColor("white"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(0, 0, w, h)
    if is_dark():
        g.setColorAt(0, QColor("#1E1F22"))
        g.setColorAt(0.65, QColor("#2B2D30"))
        g.setColorAt(1, QColor("#2D4A80"))
    else:
        g.setColorAt(0, QColor("#1F388C"))
        g.setColorAt(1, QColor("#2E8C80"))
    p.fillRect(0, 0, w, h, g)
    p.setBrush(QColor(255, 255, 255, 14 if is_dark() else 40))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(w - 210, -90, 320, 320))
    p.drawEllipse(QRectF(-80, h - 120, 220, 220))
    logo = QPixmap(asset("app_icon_256.png")).scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation)
    p.drawPixmap(40, 90, logo)
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI", 30, QFont.Weight.Black))
    p.drawText(QRectF(225, 105, 380, 60), Qt.AlignmentFlag.AlignLeft, "HadaraLab")
    p.setFont(QFont("Segoe UI", 10))
    p.drawText(QRectF(228, 168, 380, 50), Qt.AlignmentFlag.AlignLeft,
               f"Version {__version__}  ·  Al-Hadara University College\nComputer Techniques Engineering")
    p.end()
    return pm


SERVER_NAME = "HadaraLab-" + (os.environ.get("USERNAME") or "user")


def script_args(argv):
    return [os.path.abspath(a) for a in argv if a.lower().endswith(".m") and os.path.isfile(a)]


def send_to_running(paths):
    """Double-clicking a .m file while HadaraLab is open: hand the file to that window."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(500):
        return False
    sock.write(QByteArray("\n".join(paths).encode("utf-8")))
    sock.flush()
    sock.waitForBytesWritten(1000)
    sock.disconnectFromServer()
    return True


def listen_for_files(win):
    server = QLocalServer(win)
    QLocalServer.removeServer(SERVER_NAME)        # left over after a crash
    server.listen(SERVER_NAME)

    def accept():
        sock = server.nextPendingConnection()

        def read():
            for path in bytes(sock.readAll()).decode("utf-8", "replace").splitlines():
                if os.path.isfile(path):
                    win.open_path(path)
            win.setWindowState(win.windowState() & ~Qt.WindowState.WindowMinimized)
            win.raise_()
            win.activateWindow()

        sock.readyRead.connect(read)
        sock.disconnected.connect(sock.deleteLater)

    server.newConnection.connect(accept)
    return server


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("HadaraLab")
    app.setWindowIcon(QIcon(asset("app_icon.ico")))
    app.setStyle("Fusion")
    files = script_args(sys.argv[1:])
    if files and send_to_running(files):
        return
    # bundled code font (JetBrains Mono, SIL OFL 1.1) so every student sees the same editor
    fonts = asset("fonts")
    for name in sorted(os.listdir(fonts)) if os.path.isdir(fonts) else []:
        if name.endswith(".ttf"):
            QFontDatabase.addApplicationFont(os.path.join(fonts, name))
    load_saved_theme()                 # chosen in Settings > Theme
    app.setStyleSheet(build_style())

    splash = QSplashScreen(make_splash())
    splash.show()
    app.processEvents()

    from hadaralab.ui.main_window import MainWindow
    win = MainWindow()

    win.file_server = listen_for_files(win)
    for path in files:
        win.open_path(path)

    def show():
        win.showMaximized()
        splash.finish(win)
        QTimer.singleShot(300, win.offer_recovery)

    QTimer.singleShot(900, show)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
