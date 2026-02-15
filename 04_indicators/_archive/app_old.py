"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR EDGE TESTING v1.0
Application Entry Point
XIII Trading LLC
================================================================================

Launches the PyQt6 Indicator Edge Testing GUI.

Usage:
    python app.py                    # Launch GUI
    python scripts/run_edge_tests.py # CLI mode (for automation)

================================================================================
"""
import sys
from pathlib import Path

# Add indicator_gui to path
gui_path = Path(__file__).parent / "indicator_gui"
sys.path.insert(0, str(gui_path))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from main_window import IndicatorEdgeWindow


def main():
    """Main entry point."""
    app = QApplication(sys.argv)

    # Set application-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Create and show window
    window = IndicatorEdgeWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
