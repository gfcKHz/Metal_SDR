#!/usr/bin/env python3
"""Dynamic Spectrum Access Simulation"""

import numpy as np
from ..sensing.energy_detector import energy_detector

def simulate_dynamic_access(iq_data: np.ndarray, sample_rate: float, channels: list[float]) -> float:
    """
    Simulate cognitive radio: Sense channels and allocate the first free one

    Args:
        iq_data: Complex IQ samples (simulated multi-channel)
        sample_rate: Sample rate in Hz
        channels: List of center frequencies to sense

    Returns:
        float: Allocated channel frequency, or -1 if all occupied
    """
    for ch_freq in channels:
        # Simulate sensing (in practice, capture for each channel)
        occupied = energy_detector(iq_data, -60.0)
        if not occupied:
            print(f"Allocating channel at {ch_freq/1e6:.1f} MHz")
            return ch_freq
    return -1.0

if __name__ == "__main__":
    # Example usage
    sample_data = np.random.randn(1000) + 1j * np.random.randn(1000)
    channels = [100e6, 105e6, 110e6]
    allocated = simulate_dynamic_access(sample_data, 2.4e6, channels)
    print(f"Allocated: {allocated/1e6:.1f} MHz")
