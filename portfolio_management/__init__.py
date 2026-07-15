"""Portfolio Management Package"""

__version__ = "0.1.0"

# Import main modules for easy access
from .config import load_env as _load_env
from .dataloader import create_data_loader
from .eda import PlotAnalyzer, DistributionAnalyzer, TimeSeriesAnalyzer
from .tsm import ARIMAGARCHPredictor, GARCHPredictor, MarkovSwitchingGARCHPredictor, RegimeDetector
from .strategy import MomentumStrategy

# Load a local .env file (if present) so credentials can live there instead of
# being exported by hand. Loaders read env vars lazily at construction, so
# doing this after imports is fine. Real environment variables take precedence.
_load_env()

__all__ = [
    "create_data_loader",
    "PlotAnalyzer",
    "DistributionAnalyzer",
    "TimeSeriesAnalyzer",
    "GARCHPredictor",
    "ARIMAGARCHPredictor",
    "MarkovSwitchingGARCHPredictor",
    "RegimeDetector",
    "MomentumStrategy",
]
