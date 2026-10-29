"""Light and dark themes: colors and the application style sheet.

The UI is written with the light colors below. In dark mode every light color
is translated through DARK_MAP (Qt style sheets, QColors and matplotlib
artists alike), so the same widgets render in either theme.

The dark theme is a neutral graphite palette in the spirit of JetBrains'
New UI and VS Code Dark Modern: dark gray instead of pure black, lighter
surfaces for raised elements, muted accents, and Dark+ syntax colors.
"""

import os
import re

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")

# named dark-theme colors (also used directly by plots, icons and the splash)
DARK_UI = {
    "window": "#1E1F22",      # app background
    "surface": "#2B2D30",     # panels, inputs, plot background
    "raised": "#313337",      # hover / raised controls
    "border": "#393B40",
    "text": "#DFE1E5",
    "text2": "#B4B8BF",
    "muted": "#8C9098",
    "grid": "#35373C",
    "spine": "#4E5157",
    "accent": "#3574F0",
}

# light color -> dark color
DARK_MAP = {
    # surfaces (darkest = window, lighter = raised)
    "#FFFFFF": "#2B2D30", "WHITE": "#2B2D30", "#F3F7FC": "#1E1F22", "#F3F8FF": "#26282C",
    "#F5F9FE": "#232427", "#F5FAFF": "#313337", "#F2F8FF": "#26282E", "#EEF4FB": "#2F3134",
    "#EEF3F9": "#303236", "#E8F0FA": "#232427", "#E8F1FD": "#393B40", "#D6E8FD": "#43454A",
    "#D6EAFE": "#2E436E", "#E3ECF7": "#3C3E43", "#E3EBF5": "#35373C", "#DCE6F2": "#393B40",
    "#C9D7E8": "#4A4C51", "#9FB7D3": "#5E6167", "#B8C7D9": "#4E5157",
    # status backgrounds and borders (muted tints)
    "#FFFDE7": "#3A3524", "#FFF6E5": "#38301F", "#FDECEF": "#3B2427", "#FFF0F3": "#3A2427",
    "#FFE3E8": "#4A2A2E", "#E8F8F0": "#21322A", "#FFCC80": "#6B5530", "#F48FB1": "#6B3A40",
    "#A5D6A7": "#355E44", "#CDE8CF": "#355E44", "#F4FBF4": "#21322A", "#E8F6E9": "#263A2F",
    "#F8FBFF": "#2B2D30", "#EEF6FF": "#313337",
    # text
    "#24324A": "#DFE1E5", "#4A5B73": "#B4B8BF", "#6B7C93": "#8C9098", "#6C8299": "#8C9098",
    "#7A8BA3": "#868A91", "#8A9AB0": "#868A91", "#9AA8BA": "#7A7E85", "#9AAAC0": "#6F737A",
    "#9FB3C8": "#55585E", "#212121": "#DFE1E5", "#000000": "#DFE1E5",
    # accents (desaturated) - blue, teal, orange, pink, purple, green, red
    "#1E88E5": "#4A86F0", "#2196F3": "#5C93F2", "#00BFA5": "#3FB8A2", "#1DE9B6": "#55C7B2",
    "#FF8F00": "#D9822B", "#FFA000": "#E8963A", "#FF6D00": "#E8913A", "#E65100": "#E2A04A",
    "#E91E63": "#E0679A", "#C62828": "#EF7A80", "#E53935": "#E5534B", "#F4511E": "#E5734B",
    "#7C4DFF": "#9D7CD8", "#43A047": "#6AAB73", "#00ACC1": "#56B6C2", "#FFB300": "#E5C07B",
    "#FDD835": "#E5C07B",
    # titles / keywords and the other syntax colors follow VS Code Dark+
    "#1565C0": "#569CD6",     # titles, keywords
    "#00897B": "#4EC9B0",     # built-in functions
    "#D81B60": "#DCDCAA",     # control functions (tf, step, bode ...)
    "#EF6C00": "#B5CEA8",     # numbers
    "#8E24AA": "#CE9178",     # strings
    "#2E7D32": "#6A9955",     # section comments, "stable" text
}
LIGHT_MAP = {v: k for k, v in DARK_MAP.items() if k.startswith("#")}

_theme = {"name": "light"}


def theme_name():
    return _theme["name"]


def is_dark():
    return _theme["name"] == "dark"


def set_theme(name):
    _theme["name"] = "dark" if name == "dark" else "light"


def themed_color(color):
    """Translate one light color to the current theme."""
    if not is_dark() or not isinstance(color, str):
        return color
    return DARK_MAP.get(color.strip().upper(), color)


# "white" is only translated as a background; white text on colored buttons stays white
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b|(?<=background: )white\b|(?<=background:)white\b")


def themed(css):
    """Translate every light color inside a style sheet or HTML string."""
    if not is_dark() or not css:
        return css
    return _HEX_RE.sub(lambda m: DARK_MAP.get(m.group().upper(), m.group()), css)


def load_saved_theme():
    """Read the theme chosen in Settings (applied at start-up)."""
    from PySide6.QtCore import QSettings
    set_theme(QSettings("Hadara", "HadaraLab").value("theme", "light"))
    return theme_name()


def save_theme(name):
    from PySide6.QtCore import QSettings
    QSettings("Hadara", "HadaraLab").setValue("theme", name)


def qc(*args):
    """QColor in the current theme (accepts a light hex color)."""
    from PySide6.QtGui import QColor
    if len(args) == 1 and isinstance(args[0], str):
        return QColor(themed_color(args[0]))
    return QColor(*args)


def set_css(widget, css):
    """Apply a widget style sheet in the current theme."""
    widget.setStyleSheet(themed(css))


C = {
    "bg": "#F3F7FC",
    "panel": "#FFFFFF",
    "border": "#DCE6F2",
    "text": "#24324A",
    "muted": "#6B7C93",
    "primary": "#1E88E5",
    "primary_dark": "#1565C0",
    "teal": "#00BFA5",
    "orange": "#FF8F00",
    "pink": "#E91E63",
    "purple": "#7C4DFF",
    "green": "#43A047",
    "red": "#E53935",
    "select": "#D6EAFE",
    "current_line": "#F2F8FF",
    "header_a": "#1E88E5",
    "header_b": "#00BFA5",
}

CODE_FONT = "Cascadia Mono, Consolas, Courier New"
UI_FONT = "Segoe UI"


def asset(name):
    return os.path.join(ASSETS, name)


ARROW_DOWN = asset("arrow_down.svg").replace("\\", "/")
ARROW_UP = asset("arrow_up.svg").replace("\\", "/")


def build_style():
    """Application style sheet for the current theme."""
    css = themed(STYLE)
    if is_dark():
        css = css.replace(ARROW_DOWN, asset("arrow_down_dark.svg").replace("\\", "/"))
        css = css.replace(ARROW_UP, asset("arrow_up_dark.svg").replace("\\", "/"))
        css += DARK_EXTRA
    return css


# small dark-only refinements on top of the translated light style sheet
DARK_EXTRA = f"""
QWidget#Header {{
    background: {DARK_UI['surface']};
    border-bottom: 1px solid {DARK_UI['border']};
}}
QSlider::handle:horizontal {{ background: {DARK_UI['text']}; border: 2px solid {DARK_UI['accent']}; }}
QToolButton[class="HeaderButton"] {{
    background: {DARK_UI['raised']};
    border: 1px solid {DARK_UI['border']};
    color: {DARK_UI['text']};
}}
QToolButton[class="HeaderButton"]:hover {{ background: #3A3D42; border-color: #4A4D53; }}
QToolButton[class="HeaderButton"]:pressed {{ background: #44474D; }}
QToolButton#StopButton:disabled {{ background: {DARK_UI['raised']}; color: #6F737A; }}
QLabel#AppTitle {{ color: {DARK_UI['text']}; }}
QMenuBar {{ background: {DARK_UI['window']}; }}
QStatusBar {{ background: {DARK_UI['window']}; }}
QToolTip {{ background: {DARK_UI['raised']}; color: {DARK_UI['text']}; border: 1px solid {DARK_UI['border']}; }}
"""


STYLE = f"""
* {{
    font-family: "{UI_FONT}";
    font-size: 10pt;
    color: {C['text']};
}}
QMainWindow, QDialog {{
    background: {C['bg']};
}}
QWidget#Header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {C['header_a']}, stop:1 {C['header_b']});
}}
QWidget#Header QLabel {{
    color: white;
}}
QLabel#AppTitle {{
    font-size: 15pt;
    font-weight: 700;
    color: white;
}}
QLabel#AppSubtitle {{
    font-size: 9pt;
    color: rgba(255,255,255,0.88);
}}
QToolButton.HeaderButton, QToolButton[class="HeaderButton"] {{
    color: white;
    background: rgba(255,255,255,0.16);
    border: 1px solid rgba(255,255,255,0.35);
    border-radius: 9px;
    padding: 6px 12px;
    font-weight: 600;
}}
QToolButton[class="HeaderButton"]:hover {{
    background: rgba(255,255,255,0.30);
}}
QToolButton[class="HeaderButton"]:pressed {{
    background: rgba(255,255,255,0.45);
}}
QToolButton#RunButton {{
    color: white;
    background: {C['orange']};
    border: none;
    border-radius: 9px;
    padding: 6px 16px;
    font-weight: 700;
}}
QToolButton#RunButton:hover {{ background: #FFA000; }}
QToolButton#RunButton:disabled {{ background: #FFCC80; }}
QToolButton#StopButton {{
    color: white;
    background: {C['pink']};
    border: none;
    border-radius: 9px;
    padding: 6px 14px;
    font-weight: 700;
}}
QToolButton#StopButton:disabled {{ background: rgba(255,255,255,0.18); color: rgba(255,255,255,0.6); }}

QFrame.Card, QFrame[class="Card"] {{
    background: {C['panel']};
    border: 1px solid {C['border']};
    border-radius: 12px;
}}
QLabel.PanelTitle, QLabel[class="PanelTitle"] {{
    font-weight: 700;
    color: {C['primary_dark']};
    padding: 2px 4px;
}}

QTabWidget::pane {{
    border: 1px solid {C['border']};
    border-radius: 10px;
    background: {C['panel']};
    top: -1px;
}}
QTabBar::tab {{
    background: #E8F0FA;
    border: 1px solid {C['border']};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 6px 14px;
    margin-right: 3px;
    color: {C['muted']};
}}
QTabBar::tab:selected {{
    background: {C['panel']};
    color: {C['primary_dark']};
    font-weight: 600;
}}
QTabBar::tab:hover {{ color: {C['primary']}; }}

QPlainTextEdit, QTextEdit, QLineEdit, QTableWidget, QTreeView, QListWidget {{
    background: {C['panel']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    selection-background-color: {C['select']};
    selection-color: {C['text']};
}}
QLineEdit {{ padding: 5px 8px; }}
QLineEdit:focus, QPlainTextEdit:focus {{ border: 1px solid {C['primary']}; }}

QHeaderView::section {{
    background: #EEF4FB;
    border: none;
    border-bottom: 1px solid {C['border']};
    padding: 5px;
    font-weight: 600;
    color: {C['muted']};
}}
QTableWidget {{ gridline-color: #EEF3F9; }}

QPushButton {{
    background: {C['primary']};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{ background: #2196F3; }}
QPushButton:pressed {{ background: {C['primary_dark']}; }}
QPushButton[flat="true"], QPushButton.Secondary, QPushButton[class="Secondary"] {{
    background: #E8F1FD;
    color: {C['primary_dark']};
}}
QPushButton[class="Secondary"]:hover {{ background: #D6E8FD; }}
QPushButton[class="Teal"] {{ background: {C['teal']}; }}
QPushButton[class="Teal"]:hover {{ background: #1DE9B6; color: {C['text']}; }}
QPushButton[class="Orange"] {{ background: {C['orange']}; }}
QPushButton[class="Pink"] {{ background: {C['pink']}; }}
QPushButton[class="Purple"] {{ background: {C['purple']}; }}

QComboBox, QSpinBox, QDoubleSpinBox {{
    background: white;
    border: 1px solid {C['border']};
    border-radius: 7px;
    padding: 4px 8px;
    min-height: 22px;
}}
QComboBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {C['primary']}; }}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: url("{ARROW_DOWN}");
    width: 10px; height: 6px;
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: white;
    border: 1px solid {C['border']};
    selection-background-color: {C['select']};
    selection-color: {C['text']};
    outline: none;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    border: none;
    background: transparent;
    width: 18px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {C['select']};
    border-radius: 4px;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url("{ARROW_UP}");
    width: 8px; height: 5px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url("{ARROW_DOWN}");
    width: 8px; height: 5px;
}}
QHeaderView {{ background: white; border: none; }}
QHeaderView::section:vertical {{
    background: #F5F9FE;
    border: none;
    border-right: 1px solid {C['border']};
    padding: 0 8px;
    color: {C['primary_dark']};
}}
QTableCornerButton::section {{
    background: #EEF4FB;
    border: none;
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: #E3ECF7;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {C['primary']}, stop:1 {C['teal']});
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: white;
    border: 2px solid {C['primary']};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 9px;
}}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 8px; }}
QSplitter::handle:vertical {{ height: 8px; }}

QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #C9D7E8;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #9FB7D3; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #C9D7E8;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QMenuBar {{
    background: white;
    border-bottom: 1px solid {C['border']};
}}
QMenuBar::item {{ padding: 5px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: {C['select']}; border-radius: 6px; }}
QMenu {{
    background: white;
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {C['select']}; }}
QMenu::separator {{ height: 1px; background: {C['border']}; margin: 4px 8px; }}

QStatusBar {{
    background: white;
    border-top: 1px solid {C['border']};
    color: {C['muted']};
}}
QToolTip {{
    background: white;
    color: {C['text']};
    border: 1px solid {C['border']};
    padding: 5px;
    border-radius: 6px;
}}
QGroupBox {{
    background: white;
    border: 1px solid {C['border']};
    border-radius: 10px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {C['primary_dark']};
}}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
"""
