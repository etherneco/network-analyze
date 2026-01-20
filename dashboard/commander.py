import threading
from typing import Optional, Callable
from PyQt6 import QtCore, QtGui, QtWidgets
from . import network_data as nd

class CommanderPanel(QtWidgets.QWidget):
    def __init__(self, status_setter: Optional[Callable[[str], None]] = None, parent=None):
        super().__init__(parent)
        self.status_setter = status_setter
        self.host = None
        self.ip = None
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.setLayout(self.layout)
        self.buttons = []
        self.setMinimumWidth(260)
        self._title = QtWidgets.QLabel("Commander")
        self._title.setObjectName("title")
        self.layout.addWidget(self._title)
        self.layout.addStretch()

    def setTarget(self, hostname: Optional[str], ip: Optional[str]):
        if hostname == self.host and ip == self.ip: return
        self.host = hostname; self.ip = ip
        for b in self.buttons:
            try: self.layout.removeWidget(b); b.deleteLater()
            except: pass
        self.buttons = []
        actions = nd.COMMANDS.get(hostname, [])
        idx = 1
        for action in actions:
            btn = QtWidgets.QPushButton(action["label"])
            btn.setMinimumHeight(40)
            btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet("QPushButton { background-color: #2A6CFF; color: white; border-radius: 6px; font-size: 16px; padding: 6px; } QPushButton:hover { background-color: #4A82FF; }")
            cmd = action.get("cmd", "")
            btn.clicked.connect(lambda _, c=cmd: self._on_click(c))
            self.layout.insertWidget(idx, btn); self.buttons.append(btn); idx+=1
        if not actions:
            lbl = QtWidgets.QLabel("No actions" if hostname else "No host")
            lbl.setStyleSheet("color: #9FA3A7;"); self.layout.insertWidget(idx, lbl); self.buttons.append(lbl)

    def _on_click(self, cmd: str):
        if not self.host or not self.ip:
            if self.status_setter: self.status_setter("No host selected")
            return
        threading.Thread(target=self._send, args=(self.ip, self.host, cmd), daemon=True).start()

    def _send(self, ip, host, cmd):
        msg = nd.send_command_to_server(ip, host, cmd)
        if self.status_setter: self.status_setter(f"Cmd '{cmd}': {msg}")
