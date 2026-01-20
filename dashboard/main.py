#!/usr/bin/env python3
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
