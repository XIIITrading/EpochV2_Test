"""
Dark Theme Stylesheet
Epoch Trading System v2.0 - XIII Trading LLC

Re-exports from shared infrastructure.
All colors and styles are defined in 00_shared/ui/styles.py.
"""

import importlib.util
from pathlib import Path

# Load shared styles by explicit file path to avoid circular import
_shared_styles_path = Path(__file__).parent.parent.parent / "00_shared" / "ui" / "styles.py"
_spec = importlib.util.spec_from_file_location("shared_ui_styles", _shared_styles_path)
_shared_styles = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared_styles)

COLORS = _shared_styles.COLORS
DARK_STYLESHEET = _shared_styles.DARK_STYLESHEET
CELL_STYLES = _shared_styles.CELL_STYLES
get_delta_style = _shared_styles.get_delta_style
get_score_style = _shared_styles.get_score_style
get_direction_style = _shared_styles.get_direction_style

__all__ = ['COLORS', 'DARK_STYLESHEET', 'CELL_STYLES',
           'get_delta_style', 'get_score_style', 'get_direction_style']
