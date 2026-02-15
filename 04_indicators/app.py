"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR ANALYSIS v2.0
Entry Point
XIII Trading LLC
================================================================================

Three-phase indicator analysis viewer:
- Ramp-Up (25 bars before entry)
- Entry Snapshot (1 bar at entry)
- Post-Trade (25 bars after entry)

Usage:
    python 04_indicators/app.py
"""
import sys
import os
from pathlib import Path

# Environment
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# Path setup
MODULE_DIR = Path(__file__).parent
ROOT_DIR = MODULE_DIR.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(MODULE_DIR))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Epoch Indicator Analysis")
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
