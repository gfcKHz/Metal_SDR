# models.py
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Optional

@dataclass(frozen=True, slots=True)
class Capture:
    """Immutable capture artifact - hashable for deduplication"""
    data_path: Path
    meta_path: Path
    center_freq: float
    sample_rate: float
    duration: float
    sha256: str
    timestamp: datetime
    
    @property
    def freq_mhz(self) -> float:
        return self.center_freq / 1e6
    
    @property 
    def sample_rate_mhz(self) -> float:
        return self.sample_rate / 1e6