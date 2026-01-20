import time
import threading
from PyQt6 import QtCore, QtWidgets

import config
from . import network_data as nd
from .widgets import (
    CircularGauge,
    DiskList,
    LiveScreenView,
    LoadingSpinner,
    MemoryBar,
    ProcessTable,
    human_size,
)
from .commander import CommanderPanel

REFRESH_INTERVAL_SEC = config.DASHBOARD_REFRESH_INTERVAL_SEC

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
        # KOLUMNA 1: Stats (CPU + MEMORY + DISK)
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

        # Dysk
        disk_card = QtWidgets.QFrame(); disk_card.setObjectName("card"); disk_l = QtWidgets.QVBoxLayout(disk_card)
        disk_l.addWidget(QtWidgets.QLabel("Disk Storage", objectName="title"))
        self.disk_list = DiskList(); disk_l.addWidget(self.disk_list)
        col1_l.addWidget(disk_card, 1)


        # -----------------------------------------------
        # KOLUMNA 2: Live Screen View (CENTER)
        # -----------------------------------------------
        screen_card = QtWidgets.QFrame(); screen_card.setObjectName("card"); screen_l = QtWidgets.QVBoxLayout(screen_card)
        screen_l.addWidget(QtWidgets.QLabel("Remote Screen (10s refresh)", objectName="title"))
        
        self.screen_view = LiveScreenView()
        screen_l.addWidget(self.screen_view)
        
        panels_layout.addWidget(screen_card, 2) # Szersze niż reszta

        # -----------------------------------------------
        # KOLUMNA 3: Processes + Commander
        # -----------------------------------------------
        col3 = QtWidgets.QWidget(); col3_l = QtWidgets.QVBoxLayout(col3); col3_l.setContentsMargins(0,0,0,0); col3_l.setSpacing(15)
        
        # Commander
        cmd_card = QtWidgets.QFrame(); cmd_card.setObjectName("card"); cmd_l = QtWidgets.QVBoxLayout(cmd_card)
        cmd_l.addWidget(QtWidgets.QLabel("Commander", objectName="title"))
        self.commander = CommanderPanel(status_setter=self._set_status)
        cmd_l.addWidget(self.commander)
        col3_l.addWidget(cmd_card, 1)

        # Lista Procesów
        proc_card = QtWidgets.QFrame(); proc_card.setObjectName("card"); proc_l = QtWidgets.QVBoxLayout(proc_card)
        proc_l.addWidget(QtWidgets.QLabel("Top Processes", objectName="title"))
        self.proc_table = ProcessTable()
        proc_l.addWidget(self.proc_table)
        col3_l.addWidget(proc_card, 2) # Dajemy jej więcej miejsca w pionie
                
        panels_layout.addWidget(col3, 1)

        main_layout.addWidget(self.panels_widget)
        self.panels_widget.setVisible(False)
        self.status = QtWidgets.QLabel("Initializing..."); main_layout.addWidget(self.status)
        
        self._metrics = None; self._current_host = None; self._current_ip = None; self._fetch_lock = threading.Lock()
        
        self._clock_timer = QtCore.QTimer(self); self._clock_timer.setInterval(1000); self._clock_timer.timeout.connect(self._update_clock); self._clock_timer.start()
        self._refresh_timer = QtCore.QTimer(self); self._refresh_timer.setInterval(int(REFRESH_INTERVAL_SEC * 1000)); self._refresh_timer.timeout.connect(self._trigger_fetch); self._refresh_timer.start()
        self._trigger_fetch()

    def _base_stylesheet(self):
        return """
        QWidget { background: #101214; color: #E6E8EB; font-family: Inter, Arial; }
        #card { background: #131517; border-radius: 12px; padding: 12px; }
        #title { font-size: 20px; font-weight: 600; color: #E6E8EB; margin-bottom: 5px; }
        #bigHost { font-size: 36px; font-weight: 700; color: #FFFFFF; letter-spacing: 1px; }
        #ipLabel { font-size: 16px; font-weight: 400; color: #9FA3A7; }
        #timeLabel { font-size: 16px; color: #B4B9BD; }
        QLabel { color: #C8CDD0; }
        """

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
