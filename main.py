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

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
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
        g.setColorAt(0, QColor("#1E88E5"))
        g.setColorAt(1, QColor("#00BFA5"))
    p.fillRect(0, 0, w, h, g)
    p.setBrush(QColor(255, 255, 255, 14 if is_dark() else 40))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(w - 210, -90, 320, 320))
    p.drawEllipse(QRectF(-80, h - 120, 220, 220))
    logo = QPixmap(asset("logo_256.png")).scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
    p.setBrush(QColor("white"))
    p.drawEllipse(QRectF(38, 88, 164, 164))
    p.drawPixmap(45, 95, logo)
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI", 30, QFont.Weight.Black))
    p.drawText(QRectF(225, 105, 380, 60), Qt.AlignmentFlag.AlignLeft, "HadaraLab")
    p.setFont(QFont("Segoe UI", 10))
    p.drawText(QRectF(228, 168, 380, 50), Qt.AlignmentFlag.AlignLeft,
               f"Version {__version__}  ·  Al-Hadara University College\nComputer Techniques Engineering")
    p.end()
    return pm


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("HadaraLab")
    app.setWindowIcon(QIcon(asset("app_icon.ico")))
    app.setStyle("Fusion")
    load_saved_theme()                 # chosen in Settings > Theme
    app.setStyleSheet(build_style())

    splash = QSplashScreen(make_splash())
    splash.show()
    app.processEvents()

    from hadaralab.ui.main_window import MainWindow
    win = MainWindow()

    for arg in sys.argv[1:]:
        if arg.lower().endswith(".m") and os.path.isfile(arg):
            win.open_path(arg)

    def show():
        win.showMaximized()
        splash.finish(win)

    QTimer.singleShot(900, show)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
