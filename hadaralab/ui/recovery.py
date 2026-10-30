"""Crash / power-cut recovery for unsaved scripts.

While HadaraLab runs, the text of every script with unsaved changes is copied every
few seconds to a session folder under %LOCALAPPDATA%\\HadaraLab\\recovery. A normal exit
deletes that folder. If the program closed unexpectedly, the folder is still there on
the next start and its scripts are offered back to the user.

Each running copy of the program has its own session folder, guarded by a QLockFile, so
two open windows never delete or restore each other's files.
"""

import json
import os
import shutil
import uuid

from PySide6.QtCore import QLockFile

STATE_FILE = "scripts.json"


def recovery_root():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    return os.path.join(base, "HadaraLab", "recovery")


class RecoverySession:
    def __init__(self, root=None):
        self.root = root or recovery_root()
        self.dir = os.path.join(self.root, f"session-{os.getpid()}-{uuid.uuid4().hex[:8]}")
        os.makedirs(self.dir, exist_ok=True)
        self.lock = QLockFile(os.path.join(self.dir, "lock"))
        self.lock.setStaleLockTime(0)          # stale only when the owning process is gone
        self.lock.tryLock(0)
        self._last = None

    # -- this session --------------------------------------------------------
    def save(self, scripts):
        """scripts: list of {"path": str|None, "title": str, "text": str}."""
        data = json.dumps(scripts, ensure_ascii=False)
        if data == self._last:
            return
        tmp = os.path.join(self.dir, STATE_FILE + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, os.path.join(self.dir, STATE_FILE))   # never leaves a half-written file
        self._last = data

    def close(self):
        """Normal exit: nothing to recover."""
        self.lock.unlock()
        shutil.rmtree(self.dir, ignore_errors=True)

    # -- earlier sessions ----------------------------------------------------
    def orphans(self):
        """Folders left by copies of HadaraLab that did not close normally."""
        found = []
        if not os.path.isdir(self.root):
            return found
        for name in sorted(os.listdir(self.root)):
            d = os.path.join(self.root, name)
            if d == self.dir or not os.path.isdir(d):
                continue
            lock = QLockFile(os.path.join(d, "lock"))
            lock.setStaleLockTime(0)
            if not lock.tryLock(0):            # that copy of the program is still open
                continue
            lock.unlock()
            found.append(d)
        return found

    def load(self, folders):
        scripts = []
        for d in folders:
            try:
                with open(os.path.join(d, STATE_FILE), encoding="utf-8") as fh:
                    items = json.load(fh)
            except (OSError, ValueError):
                continue
            scripts.extend(s for s in items if isinstance(s, dict) and isinstance(s.get("text"), str))
        return scripts

    @staticmethod
    def discard(folders):
        for d in folders:
            shutil.rmtree(d, ignore_errors=True)
