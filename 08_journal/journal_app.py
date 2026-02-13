"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 08: JOURNAL TRADE VIEWER v1.0
Application Entry Point
XIII Trading LLC
================================================================================

Launches the PyQt6 Journal Trade Viewer GUI.

Displays FIFO trades from journal_trades table with full chart analysis:
- All 7 chart types (Daily, H1 Prior, H1, M15, M5 Entry, M1 Action, M1 Rampup)
- TradingView Dark theme
- Entry/exit markers, zone overlays
- M5 ATR(14) stop line + R-level lines computed on-the-fly
- Volume by Price overlays

Usage:
    python journal_app.py    # Launch GUI

================================================================================
"""
import sys
import logging
from pathlib import Path

# Add viewer package to path
viewer_path = Path(__file__).parent / "viewer"
sys.path.insert(0, str(viewer_path))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S',
)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from viewer.main_window import JournalViewerWindow


def main():
    """Main entry point."""
    app = QApplication(sys.argv)

    # Set application-wide font
    font = QFont("Trebuchet MS", 10)
    app.setFont(font)

    # Create and show window
    window = JournalViewerWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
