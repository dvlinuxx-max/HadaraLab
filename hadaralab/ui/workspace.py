"""Workspace browser: lists variables with value, size and class."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from ..engine.values import class_name, inline, size_of
from .theme import qc

CLASS_COLORS = {
    "tf": "#D81B60",
    "double": "#1E88E5",
    "char": "#8E24AA",
    "struct": "#00897B",
    "logical": "#EF6C00",
    "function_handle": "#7C4DFF",
    "cell": "#43A047",
}


class WorkspaceView(QTableWidget):
    inspect = Signal(str)

    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["Name", "Value", "Class"])
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        h = self.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.cellDoubleClicked.connect(lambda r, c: self.inspect.emit(self.item(r, 0).text()))
        self.setToolTip("Double-click a variable to display it in the Command Window")

    def refresh(self, variables):
        self.setRowCount(0)
        for name in sorted(variables, key=str.lower):
            v = variables[name]
            r = self.rowCount()
            self.insertRow(r)
            cls = class_name(v)
            s = size_of(v)
            text = inline(v)
            if len(text) > 60:
                text = text[:57] + "..."
            name_item = QTableWidgetItem(name)
            name_item.setForeground(qc("#24324A"))
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)
            val_item = QTableWidgetItem(text)
            val_item.setToolTip(f"{name}: {s[0]}x{s[1]} {cls}\n{inline(v)}")
            cls_item = QTableWidgetItem(cls)
            cls_item.setForeground(qc(CLASS_COLORS.get(cls, "#6B7C93")))
            cls_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(r, 0, name_item)
            self.setItem(r, 1, val_item)
            self.setItem(r, 2, cls_item)
