import tarfile
import io
import time

# --- 1. network_data.py (Bez zmian) ---
network_data_content = """import requests
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

BARRIER_URL = "http://10.1.1.1:24802/current"

COMMANDS = {}
_last_known_host = None

@dataclass
class Metrics:
    cpu_percent: float = 0.0
    cores: int = 0
    memory_used: float = 0.0
    memory_total: float = 1.0
    swap_used: float = 0.0
    swap_total: float = 1.0
    disks: Dict[str, Dict[str, float]] = None
    processes: List[Dict] = field(default_factory=list)

    def memory_percent(self):
        return 0.0 if self.memory_total == 0 else (self.memory_used / self.memory_total) * 100.0

def fetch_host_info() -> Optional[Tuple[str, str]]:
    try:
        r = requests.get(BARRIER_URL, timeout=1.2)
        r.raise_for_status()
        data = r.json()
        server = data.get("server", {})
        name = server.get("current")
        ip = server.get("ip")
        if name and ip:
            return (name, ip)
        return None
    except Exception:
        return None

def _update_commands_cache(ip: str):
    global COMMANDS
    try:
        url = f"http://{ip}:28000/command_list"
        r = requests.get(url, timeout=2.0)
        if r.status_code == 200:
            COMMANDS.update(r.json())
    except Exception:
        pass

def fetch_remote_metrics(ip: str, hostname: str) -> Optional[Metrics]:
    global _last_known_host
    if hostname != _last_known_host:
        _update_commands_cache(ip)
        _last_known_host = hostname

    try:
        url = f"http://{ip}:28000/metrics?host={hostname}"
        r = requests.get(url, timeout=1.5)
        r.raise_for_status()
        data = r.json()
        
        m = Metrics()
        cpu = data.get("cpu", {})
        m.cpu_percent = float(cpu.get("usage_percent", 0.0))
        m.cores = cpu.get("cores", 0)
        
        mem = data.get("memory", {})
        m.memory_used = float(mem.get("used", 0.0))
        m.memory_total = float(mem.get("total", 1.0))
        
        swap = data.get("swap", {})
        m.swap_used = float(swap.get("used", 0.0))
        m.swap_total = float(swap.get("total", 1.0))
        
        m.disks = data.get("disks", {})
        m.processes = data.get("processes", [])
        
        return m
    except Exception:
        return None

def send_command_to_server(ip: str, host: str, cmd: str) -> str:
    try:
        url = f"http://{ip}:28000/command"
        payload = {"host": host, "cmd": cmd}
        r = requests.post(url, json=payload, timeout=3.0)
        try:
            r.raise_for_status()
            resp = r.json() if r.headers.get("Content-Type", "").startswith("application/json") else {"status": "ok"}
            return resp.get("message", "Command sent")
        except Exception:
            return f"HTTP {r.status_code}"
    except Exception as e:
        return str(e)
"""

# --- 2. widgets.py (LiveScreenView + ProcessTable) ---
widgets_content = """import math
import requests
import threading
import time
from typing import Dict, List
from PyQt6 import QtCore, QtGui, QtWidgets

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
        self._timer.setInterval(10000) # 10 sekund
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
            url = f"http://{self._ip}:28000/screenshot/full"
            r = requests.get(url, timeout=3.0)
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
        self.setStyleSheet(\"""
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
        \""")
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
"""

# --- 3. commander.py (Bez zmian) ---
commander_content = """import threading
from typing import Optional, Callable
from PyQt6 import QtCore, QtGui, QtWidgets
import network_data as nd

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
"""

# --- 4. dashboard.py (Nowy układ: Ekran na środku, Procesy po prawej) ---
dashboard_content = """import time
import threading
from PyQt6 import QtCore, QtWidgets

import network_data as nd
from widgets import LoadingSpinner, CircularGauge, MemoryBar, DiskList, LiveScreenView, ProcessTable, human_size
from commander import CommanderPanel

REFRESH_INTERVAL_SEC = 2.0

class DashboardWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Barrier Monitor Dashboard")
        self.setStyleSheet(self._base_stylesheet())
        self.setMinimumSize(1400, 800)
        
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # TOP
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.addStretch()
        self.time_label = QtWidgets.QLabel("--:--:--")
        self.time_label.setObjectName("timeLabel")
        top_bar.addWidget(self.time_label)
        main_layout.addLayout(top_bar)
        
        # HEADER
        header_container = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 10, 0, 30)
        header_layout.setSpacing(20)
        header_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.spinner = LoadingSpinner(); header_layout.addWidget(self.spinner)
        text_con = QtWidgets.QWidget(); text_lay = QtWidgets.QVBoxLayout(text_con); text_lay.setContentsMargins(0,0,0,0); text_lay.setSpacing(2)
        self.big_host_label = QtWidgets.QLabel("DETECTING..."); self.big_host_label.setObjectName("bigHost")
        self.ip_label = QtWidgets.QLabel("Scanning..."); self.ip_label.setObjectName("ipLabel")
        text_lay.addWidget(self.big_host_label); text_lay.addWidget(self.ip_label)
        header_layout.addWidget(text_con)
        main_layout.addWidget(header_container)
        
        # PANELS CONTAINER
        self.panels_widget = QtWidgets.QWidget()
        panels_layout = QtWidgets.QHBoxLayout(self.panels_widget)
        panels_layout.setSpacing(20)
        panels_layout.setContentsMargins(0,0,0,0)

        # -----------------------------------------------
        # KOLUMNA 1: Stats (CPU + MEMORY)
        # -----------------------------------------------
        col1 = QtWidgets.QWidget(); col1_l = QtWidgets.QVBoxLayout(col1); col1_l.setContentsMargins(0,0,0,0); col1_l.setSpacing(15)
        
        cpu_card = QtWidgets.QFrame(); cpu_card.setObjectName("card"); cpu_l = QtWidgets.QVBoxLayout(cpu_card)
        cpu_l.addWidget(QtWidgets.QLabel("CPU", objectName="title"))
        self.gauge = CircularGauge(); cpu_l.addWidget(self.gauge, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self.cpu_info = QtWidgets.QLabel("-"); cpu_l.addWidget(self.cpu_info)
        col1_l.addWidget(cpu_card)
        
        mem_card = QtWidgets.QFrame(); mem_card.setObjectName("card"); mem_l = QtWidgets.QVBoxLayout(mem_card)
        mem_l.addWidget(QtWidgets.QLabel("Memory", objectName="title"))
        self.membar = MemoryBar(); self.membar.setFixedHeight(70); mem_l.addWidget(self.membar)
        self.mem_info = QtWidgets.QLabel("-"); mem_l.addWidget(self.mem_info)
        col1_l.addWidget(mem_card)
        panels_layout.addWidget(col1, 1)

        # -----------------------------------------------
        # KOLUMNA 2: Live Screen View (CENTER)
        # -----------------------------------------------
        screen_card = QtWidgets.QFrame(); screen_card.setObjectName("card"); screen_l = QtWidgets.QVBoxLayout(screen_card)
        screen_l.addWidget(QtWidgets.QLabel("Remote Screen (10s refresh)", objectName="title"))
        
        self.screen_view = LiveScreenView()
        screen_l.addWidget(self.screen_view)
        
        panels_layout.addWidget(screen_card, 2) # Szersze niż reszta

        # -----------------------------------------------
        # KOLUMNA 3: Processes + Disk + Commander
        # -----------------------------------------------
        col3 = QtWidgets.QWidget(); col3_l = QtWidgets.QVBoxLayout(col3); col3_l.setContentsMargins(0,0,0,0); col3_l.setSpacing(15)
        
        # Lista Procesów
        proc_card = QtWidgets.QFrame(); proc_card.setObjectName("card"); proc_l = QtWidgets.QVBoxLayout(proc_card)
        proc_l.addWidget(QtWidgets.QLabel("Top Processes", objectName="title"))
        self.proc_table = ProcessTable()
        proc_l.addWidget(self.proc_table)
        col3_l.addWidget(proc_card, 2) # Dajemy jej więcej miejsca w pionie
        
        # Dysk
        disk_card = QtWidgets.QFrame(); disk_card.setObjectName("card"); disk_l = QtWidgets.QVBoxLayout(disk_card)
        disk_l.addWidget(QtWidgets.QLabel("Disk Storage", objectName="title"))
        self.disk_list = DiskList(); disk_l.addWidget(self.disk_list)
        col3_l.addWidget(disk_card, 1)
        
        # Commander
        cmd_card = QtWidgets.QFrame(); cmd_card.setObjectName("card"); cmd_l = QtWidgets.QVBoxLayout(cmd_card)
        cmd_l.addWidget(QtWidgets.QLabel("Commander", objectName="title"))
        self.commander = CommanderPanel(status_setter=self._set_status)
        cmd_l.addWidget(self.commander)
        col3_l.addWidget(cmd_card, 1)

        panels_layout.addWidget(col3, 1)

        main_layout.addWidget(self.panels_widget)
        self.panels_widget.setVisible(False)
        self.status = QtWidgets.QLabel("Initializing..."); main_layout.addWidget(self.status)
        
        self._metrics = None; self._current_host = None; self._current_ip = None; self._fetch_lock = threading.Lock()
        
        self._clock_timer = QtCore.QTimer(self); self._clock_timer.setInterval(1000); self._clock_timer.timeout.connect(self._update_clock); self._clock_timer.start()
        self._refresh_timer = QtCore.QTimer(self); self._refresh_timer.setInterval(int(REFRESH_INTERVAL_SEC * 1000)); self._refresh_timer.timeout.connect(self._trigger_fetch); self._refresh_timer.start()
        self._trigger_fetch()

    def _base_stylesheet(self):
        return \"""
        QWidget { background: #101214; color: #E6E8EB; font-family: Inter, Arial; }
        #card { background: #131517; border-radius: 12px; padding: 12px; }
        #title { font-size: 20px; font-weight: 600; color: #E6E8EB; margin-bottom: 5px; }
        #bigHost { font-size: 36px; font-weight: 700; color: #FFFFFF; letter-spacing: 1px; }
        #ipLabel { font-size: 16px; font-weight: 400; color: #9FA3A7; }
        #timeLabel { font-size: 16px; color: #B4B9BD; }
        QLabel { color: #C8CDD0; }
        \"""

    def _set_status(self, t): QtCore.QMetaObject.invokeMethod(self.status, "setText", QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(str, t))
    def _update_clock(self): self.time_label.setText(time.strftime("%H:%M:%S"))
    def _trigger_fetch(self): threading.Thread(target=self._fetch_cycle, daemon=True).start()

    def _fetch_cycle(self):
        with self._fetch_lock:
            info = nd.fetch_host_info()
            if info: self._current_host, self._current_ip = info
            new_metrics = None
            if self._current_ip: new_metrics = nd.fetch_remote_metrics(self._current_ip, self._current_host)
            QtCore.QMetaObject.invokeMethod(self, "_apply_state", QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(object, new_metrics))

    @QtCore.pyqtSlot(object)
    def _apply_state(self, metrics: nd.Metrics):
        self._metrics = metrics
        if metrics:
            self.spinner.setVisible(False); self.panels_widget.setVisible(True)
            self.big_host_label.setText(self._current_host); self.ip_label.setText(self._current_ip)
            self.big_host_label.setStyleSheet(""); self.ip_label.setStyleSheet("#ipLabel { color: #9FA3A7; }")
            
            self.gauge.setValue(metrics.cpu_percent)
            self.membar.setPercent(metrics.memory_percent())
            self.cpu_info.setText(f"{metrics.cores} Cores / {int(metrics.cpu_percent)}% Load")
            self.mem_info.setText(f"{human_size(metrics.memory_used)} / {human_size(metrics.memory_total)}")
            self.disk_list.setDisks(metrics.disks)
            
            # Aktualizacja Tabeli Procesów
            self.proc_table.update_data(metrics.processes)
            
            # Przekazanie IP do podglądu ekranu (uruchamia timer 10s)
            self.screen_view.setIP(self._current_ip)
            
            self.status.setText(f"Status: Online — Updated: {time.strftime('%H:%M:%S')}")
            try: self.commander.setTarget(self._current_host, self._current_ip)
            except: pass
        else:
            self.spinner.setVisible(True); self.panels_widget.setVisible(False)
            if self._current_host:
                self.big_host_label.setText(self._current_host); self.ip_label.setText(f"{self._current_ip} (Offline)")
                self.spinner.setColor("#FF5555"); self.ip_label.setStyleSheet("color: #FF5555;")
            else:
                self.big_host_label.setText("SEARCHING..."); self.ip_label.setText("Waiting for Barrier...")
                self.spinner.setColor("#FFD300"); self.ip_label.setStyleSheet("color: #FFD300;")
"""

# --- 5. main.py (Bez zmian) ---
main_content = """#!/usr/bin/env python3
import sys
from PyQt6 import QtWidgets
from dashboard import DashboardWindow

def main():
    app = QtWidgets.QApplication(sys.argv)
    w = DashboardWindow()
    w.showMaximized()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
"""

def create_tar():
    files = {
        "network_data.py": network_data_content,
        "widgets.py": widgets_content,
        "commander.py": commander_content,
        "dashboard.py": dashboard_content,
        "main.py": main_content
    }

    tar_filename = "barrier_dashboard_v7.tar"
    with tarfile.open(tar_filename, "w") as tar:
        for name, content in files.items():
            encoded = content.encode('utf-8')
            tar_info = tarfile.TarInfo(name=name)
            tar_info.size = len(encoded)
            tar_info.mtime = time.time()
            tar.addfile(tar_info, io.BytesIO(encoded))
    
    print(f"Utworzono archiwum: {tar_filename}")

if __name__ == "__main__":
    create_tar()