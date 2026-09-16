"""BossForgeOS DataForge - Data processing pipeline for ML training datasets."""

from .dataforge import DataForge
from .cli import run

__version__ = "1.0.0"
__all__ = ['DataForge', 'run']
