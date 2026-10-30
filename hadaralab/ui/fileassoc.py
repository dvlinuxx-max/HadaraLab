"""Let Windows open .m files with HadaraLab (double-click / Open with).

Only the current user's registry (HKEY_CURRENT_USER\\Software\\Classes) is touched, so
no administrator rights are needed. HadaraLab is added to the "Open with" list of .m
files; it does not take over .m files from another program such as MATLAB. Windows
itself asks the user once which program should open .m files by default.

The Microsoft Store (MSIX) version declares the association in its package manifest
instead, so this module is used only by the ZIP version.
"""

import os
import sys

PROG_ID = "HadaraLab.Script"
CLASSES = r"Software\Classes"


def is_packaged():
    """True when running as the Microsoft Store (MSIX) package."""
    return "\\windowsapps\\" in os.path.abspath(sys.executable).lower()


def open_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" "%1"'
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    main = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))
    return f'"{pyw if os.path.isfile(pyw) else exe}" "{main}" "%1"'


def icon_path():
    from .theme import asset
    return asset("app_icon.ico")


def is_registered():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\{PROG_ID}\shell\open\command") as k:
            return winreg.QueryValue(k, None) == open_command()
    except OSError:
        return False


def register():
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\{PROG_ID}") as k:
        winreg.SetValue(k, None, winreg.REG_SZ, "HadaraLab script")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\{PROG_ID}\DefaultIcon") as k:
        winreg.SetValue(k, None, winreg.REG_SZ, icon_path())
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\{PROG_ID}\shell\open\command") as k:
        winreg.SetValue(k, None, winreg.REG_SZ, open_command())
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\.m\OpenWithProgids") as k:
        winreg.SetValueEx(k, PROG_ID, 0, winreg.REG_NONE, b"")
    _notify_shell()


def unregister():
    import winreg
    for sub in (r"shell\open\command", r"shell\open", "shell", "DefaultIcon", ""):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\{PROG_ID}\{sub}".rstrip("\\"))
        except OSError:
            pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{CLASSES}\.m\OpenWithProgids", 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, PROG_ID)
    except OSError:
        pass
    _notify_shell()


def _notify_shell():
    import ctypes
    SHCNE_ASSOCCHANGED, SHCNF_IDLIST = 0x08000000, 0
    ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
