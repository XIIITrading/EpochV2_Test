"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 08: FIFO TRADE PROCESSOR v1.0
Application Entry Point
XIII Trading LLC
================================================================================

Launches the PyQt6 FIFO Trade Processor GUI.

FIFO Logic:
- Each entry-side fill creates a NEW trade
- Exits close oldest open trades first (FIFO)
- Exit price per trade = VWAP of all exit portions

Usage:
    python fifo_app.py                         # Launch GUI
    python scripts/run_fifo_import.py <csv>    # CLI mode

================================================================================
"""
import sys
from pathlib import Path

# Add fifo_gui to path
gui_path = Path(__file__).parent / "fifo_gui"
sys.path.insert(0, str(gui_path))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from main_window import FIFOProcessorWindow


def main():
    """Main entry point."""
    app = QApplication(sys.argv)

    # Set application-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Create and show window
    window = FIFOProcessorWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
