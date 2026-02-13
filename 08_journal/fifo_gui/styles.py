"""
Dark Theme Stylesheet
Epoch Trading System v2.0 - XIII Trading LLC

Clean terminal-style dark theme for the FIFO Trade Processor tool.
Copied from 03_backtest/backtest_gui/styles.py for visual consistency.
"""

# Color palette
COLORS = {
    # Base colors
    'bg_primary': '#000000',      # Main background (pure black)
    'bg_secondary': '#0a0a0a',    # Panel background
    'bg_header': '#0f3460',       # Header background (blue)
    'bg_terminal': '#0a0a0a',     # Terminal background
    'border': '#2a2a4a',          # Border color
    'border_light': '#3a3a5a',    # Light border

    # Text colors
    'text_primary': '#e8e8e8',    # Primary text
    'text_secondary': '#a0a0a0',  # Secondary text
    'text_muted': '#707070',      # Muted text
    'text_terminal': '#e8e8e8',   # Terminal text (white like rest of app)

    # Status colors
    'status_ready': '#26a69a',    # Ready (green)
    'status_running': '#FFD600',  # Running (yellow)
    'status_error': '#ef5350',    # Error (red)
    'status_complete': '#26a69a', # Complete (green)

    # Progress colors
    'progress_bg': '#1a1a2e',
    'progress_fill': '#0f3460',

    # Button colors
    'button_primary': '#0f3460',
    'button_hover': '#1a4a7a',
    'button_pressed': '#0a2540',
    'button_stop': '#c62828',
    'button_stop_hover': '#e53935',
}

# Main stylesheet
DARK_STYLESHEET = f"""
/* Main Window */
QMainWindow {{
    background-color: {COLORS['bg_primary']};
}}

QWidget {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_primary']};
    font-family: 'Segoe UI', 'Consolas', monospace;
    font-size: 11px;
}}

/* Labels */
QLabel {{
    color: {COLORS['text_primary']};
    background-color: transparent;
}}

QLabel#headerLabel {{
    font-size: 20px;
    font-weight: bold;
    color: {COLORS['text_primary']};
    padding: 5px;
}}

QLabel#statusLabel {{
    font-size: 12px;
    color: {COLORS['text_secondary']};
    font-family: 'Consolas', monospace;
}}

QLabel#sectionLabel {{
    font-size: 12px;
    font-weight: bold;
    color: {COLORS['text_secondary']};
}}

/* Buttons */
QPushButton {{
    background-color: {COLORS['button_primary']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 11pt;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {COLORS['button_hover']};
    border-color: {COLORS['border_light']};
}}

QPushButton:pressed {{
    background-color: {COLORS['button_pressed']};
}}

QPushButton:disabled {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_muted']};
}}

QPushButton#processButton {{
    background-color: {COLORS['button_primary']};
    min-width: 140px;
    min-height: 40px;
    font-size: 11pt;
    padding: 10px 24px;
}}

QPushButton#saveButton {{
    background-color: #1b5e20;
    min-width: 140px;
    min-height: 40px;
    font-size: 11pt;
    padding: 10px 24px;
}}

QPushButton#saveButton:hover {{
    background-color: #2e7d32;
}}

QPushButton#saveButton:disabled {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_muted']};
}}

QPushButton#clearDbButton {{
    background-color: #444444;
    min-width: 100px;
    min-height: 40px;
    font-size: 11pt;
    padding: 10px 24px;
}}

QPushButton#clearDbButton:hover {{
    background-color: #555555;
}}

/* Combo Box */
QComboBox {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 8px 16px;
    min-width: 160px;
    min-height: 24px;
    font-size: 11pt;
}}

QComboBox:hover {{
    border-color: {COLORS['border_light']};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {COLORS['text_secondary']};
    margin-right: 5px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['button_primary']};
}}

/* Frame */
QFrame#controlPanel {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
}}

QFrame#terminalFrame {{
    background-color: {COLORS['bg_terminal']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
}}

QFrame#statusBar {{
    background-color: {COLORS['bg_secondary']};
    border-top: 1px solid {COLORS['border']};
}}

/* Text Edit (Terminal) */
QTextEdit#terminalOutput {{
    background-color: {COLORS['bg_terminal']};
    color: {COLORS['text_terminal']};
    border: none;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 10pt;
    padding: 10px;
    selection-background-color: {COLORS['button_primary']};
}}

/* Progress Bar */
QProgressBar {{
    background-color: {COLORS['progress_bg']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    text-align: center;
    color: {COLORS['text_primary']};
    font-weight: bold;
}}

QProgressBar::chunk {{
    background-color: {COLORS['progress_fill']};
    border-radius: 3px;
}}

/* Scroll Bar */
QScrollBar:vertical {{
    background-color: {COLORS['bg_secondary']};
    width: 12px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['border_light']};
    border-radius: 4px;
    min-height: 20px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['text_secondary']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
