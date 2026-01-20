import math
import requests
import threading
import time
from typing import Dict, List
from PyQt6 import QtCore, QtGui, QtWidgets

import config
def human_size(bytesize: float) -> str:
    step = 1024.0
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(bytesize)
    i = 0
    while v >= step and i < len(units)-1:
        v /= step
        i += 1
    return f"{v:.1f}{units[i]}"

# --- STANDARD WIDGETS ---
class LoadingSpinner(QtWidgets.QWidget):
    def __init__(self, p=None): super().__init__(p); self.setFixedSize(40,40); self._a=0; self._t=QtCore.QTimer(self); self._t.timeout.connect(self._r); self._t.start(40); self._c=QtGui.QColor("#2A6CFF")
    def _r(self): 
        if self.isVisible(): self._a=(self._a+15)%360; self.update()
    def setColor(self, c): self._c=QtGui.QColor(c); self.update()
    def paintEvent(self, e): p=QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing); r=self.rect().adjusted(4,4,-4,-4); pen=QtGui.QPen(self._c); pen.setWidth(4); pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap); p.setPen(pen); p.drawArc(r,-self._a*16, 270*16)

class CircularGauge(QtWidgets.QWidget):
    def __init__(self, p=None): super().__init__(p); self._v=0.0; self._t=0.0; self._tm=QtCore.QTimer(self); self._tm.timeout.connect(self._a); self.setMinimumSize(200,200)
    def setValue(self, v): self._t=max(0,min(100,float(v))); self._tm.start(16)
    def _a(self): 
        if abs(self._v-self._t)<0.1: self._v=self._t; self._tm.stop()
        else: self._v+=(self._t-self._v)*0.1
        self.update()
    def paintEvent(self, e):
        p=QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing); r=self.rect(); s=min(r.width(),r.height()); rad=s*0.38; rect=QtCore.QRectF(r.center().x()-rad, r.center().y()-rad, rad*2, rad*2)
        p.setPen(QtGui.QPen(QtGui.QColor("#1A1C1E"), rad*0.18)); p.drawEllipse(rect)
        p.setPen(QtGui.QPen(QtGui.QColor("#2A6CFF"), rad*0.18)); p.drawArc(rect, 90*16, int(-self._v/100*360*16))
        p.setPen(QtGui.QColor("#E6E8EB")); f=p.font(); f.setPointSize(28); f.setBold(True); p.setFont(f); p.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, f"{int(self._v)}%")

class MemoryBar(QtWidgets.QWidget):
    def __init__(self, p=None): super().__init__(p); self._v=0; self._t=0; self._tm=QtCore.QTimer(self); self._tm.timeout.connect(self._a)
    def setPercent(self, v): self._t=max(0,min(100,float(v))); self._tm.start(20)
    def _a(self):
        if abs(self._v-self._t)<0.1: self._v=self._t; self._tm.stop()
        else: self._v+=(self._t-self._v)*0.1
        self.update()
    def paintEvent(self, e):
        r=self.rect(); p=QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        bg=QtCore.QRectF(0, r.height()*0.25, r.width(), r.height()*0.5)
        p.setBrush(QtGui.QColor("#2B2F33")); p.setPen(QtCore.Qt.PenStyle.NoPen); p.drawRoundedRect(bg,6,6)
        p.setBrush(QtGui.QColor("#FFD300")); p.drawRoundedRect(QtCore.QRectF(bg.x(), bg.y(), bg.width()*(self._v/100), bg.height()),6,6)
        p.setPen(QtGui.QColor("#E6E8EB")); f=p.font(); f.setPointSize(14); p.setFont(f); p.drawText(r, QtCore.Qt.AlignmentFlag.AlignCenter, f"{int(self._v)}% used")

class DiskList(QtWidgets.QWidget):
    def __init__(self, p=None): super().__init__(p); self.disks={}; self.setMinimumWidth(250); self.setMinimumHeight(100)
    def setDisks(self, d): self.disks=d or {}; self.setMinimumHeight(max(100, len(self.disks)*60+20)); self.update()
    def paintEvent(self, e):
        r=self.rect(); p=QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        fm=p.font(); fm.setPointSize(12); fm.setBold(True); fs=p.font(); fs.setPointSize(10); y=5
        if not self.disks: p.setPen(QtGui.QColor("#9FA3A7")); p.drawText(r, QtCore.Qt.AlignmentFlag.AlignCenter, "No partitions"); return
        for m,i in self.disks.items():
            u,t=i.get("used",0), i.get("total",1); pct=0 if t==0 else (u/t)*100
            p.setFont(fm); p.setPen(QtGui.QColor("#E6E8EB")); p.drawText(QtCore.QRectF(10,y+2,r.width()/2,20), QtCore.Qt.AlignmentFlag.AlignLeft|QtCore.Qt.AlignmentFlag.AlignVCenter, str(m))
            p.setFont(fs); p.setPen(QtGui.QColor("#9FA3A7")); cap=f"{human_size(u)} / {human_size(t)}"; p.drawText(QtCore.QRectF(10,y+2,r.width()-20,20), QtCore.Qt.AlignmentFlag.AlignRight|QtCore.Qt.AlignmentFlag.AlignVCenter, cap)
            by=y+28; p.setPen(QtGui.QColor("#FFD300")); tw=QtGui.QFontMetrics(fs).horizontalAdvance(f"{int(pct)}%")
            p.drawText(QtCore.QRectF(r.width()-tw-10, by, tw+5, 10), QtCore.Qt.AlignmentFlag.AlignRight|QtCore.Qt.AlignmentFlag.AlignVCenter, f"{int(pct)}%")
            br=QtCore.QRectF(10,by,r.width()-tw-25,10); p.setPen(QtCore.Qt.PenStyle.NoPen); p.setBrush(QtGui.QColor("#2B2F33")); p.drawRoundedRect(br,4,4)
            fw=br.width()*(min(100,pct)/100); p.setBrush(QtGui.QColor("#2A6CFF")); 
            if fw>0: p.drawRoundedRect(QtCore.QRectF(br.x(),br.y(),fw,br.height()),4,4)
            y+=60

# --- NEW: LIVE SCREEN VIEW ---

class LiveScreenView(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setText("Waiting for connection...")
        self.setStyleSheet("background-color: #000; border-radius: 6px; border: 2px solid #333; color: #555;")
        self.setScaledContents(True) # Skaluje obrazek do rozmiaru widgetu
        self.setMinimumSize(320, 200)
        
        self._ip = None
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(config.LIVE_SCREEN_REFRESH_MS)
        self._timer.timeout.connect(self._trigger_update)
    
    def setIP(self, ip: str):
        if self._ip != ip:
            self._ip = ip
            self.setText("Loading Screen...")
            self._trigger_update()
            if not self._timer.isActive():
                self._timer.start()

    def _trigger_update(self):
        if not self._ip: return
        threading.Thread(target=self._fetch_screen, daemon=True).start()

    def _fetch_screen(self):
        try:
            # Endpoint /screenshot/full (zwraca zrzut całego ekranu)
            url = f"http://{self._ip}:{config.METRIX_SERVER_PORT}/screenshot/full"
            r = requests.get(url, timeout=config.SCREENSHOT_TIMEOUT)
            if r.status_code == 200:
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(r.content)
                QtCore.QMetaObject.invokeMethod(self, "update_pixmap", QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(QtGui.QPixmap, pixmap))
            else:
                QtCore.QMetaObject.invokeMethod(self, "show_error", QtCore.Qt.ConnectionType.QueuedConnection)
        except Exception:
            QtCore.QMetaObject.invokeMethod(self, "show_error", QtCore.Qt.ConnectionType.QueuedConnection)

    @QtCore.pyqtSlot(QtGui.QPixmap)
    def update_pixmap(self, pixmap):
        self.setPixmap(pixmap)
        self.setStyleSheet("background-color: #000; border-radius: 6px; border: 2px solid #2A6CFF;")

    @QtCore.pyqtSlot()
    def show_error(self):
        # Nie usuwamy starego obrazka, żeby nie migało, ewentualnie zmieniamy ramkę na czerwoną
        self.setStyleSheet("background-color: #000; border-radius: 6px; border: 2px solid #FF5555;")


# --- NEW: PROCESS TABLE ---

class ProcessTable(QtWidgets.QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Name", "PID", "Mem"])
        
        # Stylizacja
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(1, 60)
        self.setColumnWidth(2, 80)
        
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTableWidget {
                background-color: #131517;
                border: none;
                gridline-color: #2B2F33;
                color: #E6E8EB;
            }
            QHeaderView::section {
                background-color: #1A1C1E;
                color: #9FA3A7;
                border: none;
                padding: 4px;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 2px;
            }
            QTableWidget::item:selected {
                background-color: #2A6CFF;
                color: white;
            }
        """)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

    def update_data(self, processes: List[Dict]):
        # Zapamiętujemy scroll
        scroll_pos = self.verticalScrollBar().value()
        
        self.setRowCount(len(processes))
        for row, p in enumerate(processes):
            name_item = QtWidgets.QTableWidgetItem(str(p.get("name", "?")))
            pid_item = QtWidgets.QTableWidgetItem(str(p.get("pid", "?")))
            mem_item = QtWidgets.QTableWidgetItem(human_size(p.get("mem", 0)))
            
            # Wyrównanie
            pid_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            mem_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            
            self.setItem(row, 0, name_item)
            self.setItem(row, 1, pid_item)
            self.setItem(row, 2, mem_item)
            
        self.verticalScrollBar().setValue(scroll_pos)
