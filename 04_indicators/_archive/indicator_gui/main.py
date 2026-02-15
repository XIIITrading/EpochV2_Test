"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR EDGE TESTING v1.0
GUI Entry Point
XIII Trading LLC
================================================================================

Launches the PyQt6 Indicator Edge Testing window.
================================================================================
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from main_window import IndicatorEdgeWindow


def main():
    """Main entry point for the Indicator Edge Testing GUI."""
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
