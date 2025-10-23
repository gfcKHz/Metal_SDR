#!/usr/bin/env python3
from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np 

class SDRBackend(ABC):
    """Abstract base class for SDR hardware backends"""

    @abstractmethod
    def capture(self, center_freq: float, sample_rate: float,
                duration: float, gain: float) -> np.ndarray:
        """ 
        Capture IQ samples

        Args:
            center_freq: Center frequency in Hz
            sample_rate: Sample rate in Hz
            duration: Capture duration in seconds
            gain: Gain in dB

        Returns:
            Complex numpy array of IQ samples (complex64)
        """
        pass

    @abstractmethod
    def get_supported_sample_rates(self) -> list:
        """Return list of supported sample rates in Hz"""
        pass

    @abstractmethod
    def get_frequency_range(self) -> tuple:
        """Return list of supported sample rates in Hz"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return backend name"""
        pass

def get_backend(backend_name: str) -> SDRBackend:
    """ 
    Factory function to get SDR backend b7y name

    Args:
        backend_name: 'rtl_sdr', 'bladerf', etc.
    
    Returns:
        SDRBackend instance

    Raises:
        ValueError: If backend_name is unknown
        ImportError: If backend dependencies not installed
    """
    backend_name = backend_name.lower()

    if backend_name == "rtl_sdr":
        from backends.rtl_sdr import RTLSDRBackend
        return RTLSDRBackend()
    
    elif backend_name == "bladerf":
        from backends.bladerf import BladeRFBackend
        return BladeRFBackend()
    
    else:
        raise ValueError(
            f"Unknown backend: {backend_name}. "
            f"Supported: rtl_sdr, bladerf"
        )

def list_backends() -> dict:
    """ 
    List all available backends and their status

    Returns:
        dict mapping backend name to availability status
    """
    backends = {}
    
    # RTL-SDR
    try:
        from backends.rtl_sdr import RTLSDRBackend
        backends['rtl_sdr'] = 'available'
    except ImportError as e:
        backends['rtl_sdr'] = f'unavailable: {e}'

    # BladeRF
    try:
        from backends.bladerf import BladeRFBackend
        backends['bladerf'] = 'available'
    except ImportError as e:
        backends['bladerf'] = f'unavailable: {e}'

    return backends