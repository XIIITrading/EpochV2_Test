"""
Internal module loader for shared indicators library.
Uses importlib to load modules from absolute paths, avoiding sys.path conflicts.
"""

import importlib.util
from pathlib import Path

_LIB_DIR = Path(__file__).parent.resolve()


def _load_module(name: str, filepath: Path):
    """Load a module from an absolute file path."""
    spec = importlib.util.spec_from_file_location(name, str(filepath.resolve()))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Load config module
_config = _load_module("_shared_config", _LIB_DIR / "config.py")
CANDLE_RANGE_CONFIG = _config.CANDLE_RANGE_CONFIG
SMA_CONFIG = _config.SMA_CONFIG
VOLUME_ROC_CONFIG = _config.VOLUME_ROC_CONFIG
VOLUME_DELTA_CONFIG = _config.VOLUME_DELTA_CONFIG
CVD_CONFIG = _config.CVD_CONFIG
STRUCTURE_CONFIG = _config.STRUCTURE_CONFIG
HEALTH_CONFIG = _config.HEALTH_CONFIG
SCORE_CONFIG = _config.SCORE_CONFIG
ATR_CONFIG = _config.ATR_CONFIG

# Load utils module
_utils = _load_module("_shared_utils", _LIB_DIR / "utils.py")
get_close = _utils.get_close
get_high = _utils.get_high
get_low = _utils.get_low
get_open = _utils.get_open
get_volume = _utils.get_volume
calculate_linear_slope = _utils.calculate_linear_slope

# Load indicator_types module
_types = _load_module("_shared_types", _LIB_DIR / "indicator_types.py")
CandleRangeResult = _types.CandleRangeResult
SMAResult = _types.SMAResult
SMAMomentumResult = _types.SMAMomentumResult
VWAPResult = _types.VWAPResult
VolumeROCResult = _types.VolumeROCResult
VolumeDeltaResult = _types.VolumeDeltaResult
CVDResult = _types.CVDResult
StructureResult = _types.StructureResult
HealthResult = _types.HealthScoreResult
ScoreResult = _types.ScoreResult
ATRResult = _types.ATRResult
