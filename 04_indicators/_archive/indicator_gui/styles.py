"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR EDGE TESTING v1.0
PyQt6 Styles - Dark Theme
XIII Trading LLC
================================================================================
"""

DARK_THEME = """
QMainWindow {
    background-color: #1e1e1e;
}

QWidget {
    background-color: #1e1e1e;
    color: #e8e8e8;
    font-family: 'Segoe UI', 'Consolas', monospace;
}

QLabel {
    color: #e8e8e8;
    padding: 2px;
}

QLabel#headerLabel {
    font-size: 14px;
    font-weight: bold;
    color: #26a69a;
}

QPushButton {
    background-color: #2d2d2d;
    color: #e8e8e8;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
    min-width: 100px;
}

QPushButton:hover {
    background-color: #3d3d3d;
    border-color: #505050;
}

QPushButton:pressed {
    background-color: #1d1d1d;
}

QPushButton:disabled {
    background-color: #2d2d2d;
    color: #606060;
    border-color: #353535;
}

QPushButton#runButton {
    background-color: #26a69a;
    color: #ffffff;
    border: none;
    font-size: 12px;
}

QPushButton#runButton:hover {
    background-color: #2bbbad;
}

QPushButton#runButton:pressed {
    background-color: #1e8e82;
}

QPushButton#runButton:disabled {
    background-color: #1a5f58;
    color: #888888;
}

QPushButton#stopButton {
    background-color: #ef5350;
    color: #ffffff;
    border: none;
}

QPushButton#stopButton:hover {
    background-color: #f44336;
}

QPushButton#stopButton:disabled {
    background-color: #7a2a28;
    color: #888888;
}

QPushButton#clearButton {
    background-color: #ff9800;
    color: #ffffff;
    border: none;
}

QPushButton#clearButton:hover {
    background-color: #ffa726;
}

QTextEdit {
    background-color: #0d0d0d;
    color: #e8e8e8;
    border: 1px solid #333333;
    border-radius: 4px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    padding: 8px;
    selection-background-color: #264f78;
}

QComboBox {
    background-color: #2d2d2d;
    color: #e8e8e8;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 6px 12px;
    min-width: 120px;
}

QComboBox:hover {
    border-color: #505050;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #e8e8e8;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #e8e8e8;
    border: 1px solid #404040;
    selection-background-color: #404040;
}

QCheckBox {
    color: #e8e8e8;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #404040;
    border-radius: 3px;
    background-color: #2d2d2d;
}

QCheckBox::indicator:checked {
    background-color: #26a69a;
    border-color: #26a69a;
}

QCheckBox::indicator:hover {
    border-color: #505050;
}

QProgressBar {
    background-color: #2d2d2d;
    border: 1px solid #404040;
    border-radius: 4px;
    text-align: center;
    color: #e8e8e8;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #26a69a;
    border-radius: 3px;
}

QGroupBox {
    border: 1px solid #404040;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #26a69a;
}

QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #404040;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #505050;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 12px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #404040;
    border-radius: 6px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #505050;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QListWidget {
    background-color: #2d2d2d;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 4px;
}

QListWidget::item {
    padding: 6px;
    border-radius: 2px;
}

QListWidget::item:selected {
    background-color: #26a69a;
    color: #ffffff;
}

QListWidget::item:hover {
    background-color: #3d3d3d;
}

QDateEdit {
    background-color: #2d2d2d;
    color: #e8e8e8;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 6px 12px;
    min-width: 120px;
}

QDateEdit:hover {
    border-color: #505050;
}

QDateEdit::drop-down {
    border: none;
    width: 20px;
}

QDateEdit::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #e8e8e8;
    margin-right: 8px;
}

QCalendarWidget {
    background-color: #2d2d2d;
}

QCalendarWidget QToolButton {
    color: #e8e8e8;
    background-color: #2d2d2d;
    border: none;
    padding: 4px;
}

QCalendarWidget QToolButton:hover {
    background-color: #3d3d3d;
}

QCalendarWidget QMenu {
    background-color: #2d2d2d;
    color: #e8e8e8;
}

QCalendarWidget QSpinBox {
    background-color: #2d2d2d;
    color: #e8e8e8;
    border: 1px solid #404040;
}

QCalendarWidget QAbstractItemView:enabled {
    background-color: #2d2d2d;
    color: #e8e8e8;
    selection-background-color: #26a69a;
    selection-color: #ffffff;
}

QStatusBar {
    background-color: #252526;
    color: #808080;
    border-top: 1px solid #333333;
}
"""
