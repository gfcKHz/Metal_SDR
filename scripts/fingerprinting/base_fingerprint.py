#!/usr/bin/env python3
"""Base class for fingerprinting different modulations"""

from abc import ABC, abstractmethod
import numpy as np

class BaseFingerprint(ABC):
    """Abstract base class for signal fingerprinting"""

    @abstractmethod
    def extract_fingerprint(self, iq_data: np.ndarray, sample_rate: float, center_freq: float) -> dict:
        """
        Extract features from IQ data

        Args:
            iq_data: Complex IQ samples
            sample_rate: Sample rate in Hz
            center_freq: Center frequency in Hz

        Returns:
            dict of extracted features
        """
        pass

    def validate_quality(self, features: dict) -> dict:
        """
        Validate fingerprint quality (can be overridden)

        Returns:
            dict with 'is_reliable' bool and 'warnings' list
        """
        return {'is_reliable': True, 'warnings': []}
