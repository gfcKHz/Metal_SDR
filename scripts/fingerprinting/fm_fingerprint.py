#!/usr/bin/env python3
""" 
FM Broadcast Fingerprinting

Extracts features from IQ data to validate station identity and signal quality

Key feats:
1. Parabolic peak interpolation - Sub-bin frequency accuracy
2. CNR estimation (MPA) - Quality gate using Minimum Power Averaging
3. 3dB bandwidth measurement
4. Adjacent channel rejection
5. Spectral rolloff asymmetry

Usage:
    from fm_fingerprint import extract_fingerprint
    features = extract_fingerprint(iq_data, sample_rate, center_freq)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from scipy import signal
from sigmf import SigMFFile
import time

def load_sigmf(sigmf_path: Path) -> tuple[np.ndarray, dict]:
    """ 
    Load IQ data and metadata from SigMF fie pair

    Args:
        sigmf_path: Path to .sigmf-meta or .sigmf-data file

    Return:
        (iq_data, metadata) tuple where metadata contains:
            - sample_rate: Hz
            - center_freq: Hz
            - datatype: e.g. 'cf32_le'
    """
    # Handle both .sigmf-meta and .sigmf-data paths
    meta_path = sigmf_path.with_suffix('.sigmf-meta')

    # Load metadata
    sig = SigMFFile(str(meta_path))

    # Extract key params
    metadata = {
        'sample_rate': sig.get_global_field('core:sample_rate'),
        'center_freq': sig.get_capture_info(0).get('core:frequency'),
        'datatype': sig.get_global_field('core:datatype'),
    }

    # Load IQ data
    iq_data = sig.read_samples()

    return iq_data, metadata

def parabolic_peak_interp(freqs: np.ndarray, psd: np.ndarray) -> float:
    """ 
    Parabolic interpolation around peak to achieve sub-bin frequency accuracy

    Fits a parabola to the log-power of 3 bins around the peak to find the true
    peak frequency. Achieves ~50 Hz accuracy vs ±293 Hz bin quantization at 2.4 Mhz
    sample rate with 4096-point FFT.

    Args:
        freqs: Frequency bins in Hz
        psd: Power spectral density (linear scale)

    Returns:
        peak_freq_hz: Interpolated peak frequency in Hz
    """
    # Find bin with maximum power
    peak_idx = np.argmax(psd)

    # Need at least 1 bin on each side of parabola fit
    if peak_idx == 0 or peak_idx == len(psd) - 1:
        return freqs[peak_idx]
    
    # Get 3 bins around peak (in log scale for better fit)
    y1, y2, y3 = np.log10(psd[peak_idx-1:peak_idx+2] + 1e-12) # Add epsilon to avoid log(0)

    # Parabolic interpolation formula
    # delta = 0.5 * (y1 - y3) / (y1 - 2*y2 + y3)
    denominator = y1 - 2*y2 + y3
    if abs(denominator) < 1e-10:    # Avoid division by zero
        return freqs[peak_idx]
    
    delta = 0.5 * (y1 - y3) / denominator

    # Interpolated peak frequency
    freq_step = freqs[1] - freqs[0]
    peak_freq_hz = freqs[peak_idx] + delta * freq_step

    return peak_freq_hz

def estimate_cnr_db(freqs: np.ndarray, psd: np.ndarray, peak_freq_hz: float,
                    guard_bw_hz: float = 150e3, carrier_bw_hz: float = 50e3,
                    noise_percentile: float = 5.0) -> float:
    """ 
    Estimate Carrier-to-Noise Ratio using Minimum Power Averaging (MPA)

    Excludes guard region around carrier, then averages the quietest of 5% of
    out-of-band bins to estimate noise floor.

    Args:
        freqs: Frequency bins in Hz (centered at 0)
        psd: Power spectral density (linear scale)
        peak_freq_hz: Carrier peak frequency in Hz
        guard_bw_hz: Guard bandwidth to exclude around carrier (default: ±150 kHz)
        carrier_bw_hz: Bandwidth to integrate carrier power (default: ±50 kHz)
        noise_percentile: Percentile of quietest bins to average for noise (default: 5%)

    Return:
        cnr_db: CNR ratio in dB
    """
    # find carrier power (integrate over ±carrier_bw_hz)
    carrier_mask = np.abs(freqs - peak_freq_hz) <= carrier_bw_hz
    carrier_power = np.sum(psd[carrier_mask])

    # find noise floor (exclude guard region, average quietest bins)
    noise_mask = np.abs(freqs - peak_freq_hz) > guard_bw_hz
    noise_bins = psd[noise_mask]

    if len(noise_bins) == 0:
        return 0.0      # No noise bins available
    
    # MPA: Average quietest N% of bins
    n_bins = max(1, int(len(noise_bins) * noise_percentile / 100.0))
    noise_floor = np.mean(np.partition(noise_bins, n_bins)[:n_bins])

    # CNR in dB
    if noise_floor <= 0:
        return 100.0    # Avoid log(0)

    cnr_db = 10 * np.log10(carrier_power / noise_floor)

    return cnr_db  

def measure_bandwidth_3db(freqs: np.ndarray, psd: np.ndarray, peak_freq_hz: float) -> float:
    """ 
    Measure 3dB bandwidth of FM signal

    FM broadcast should be 180-220 kHz

    Args:
        freqs: Frequency bins in Hz
        psd: Power spectral density (linear scale)
        peak_freq_hz: Carrier peak frequency in Hz

    Returns:
        bandwidth_3db_hz: 3dB bandwidth in Hz
    """
    # Find peak power
    peak_idx = np.argmin(np.abs(freqs - peak_freq_hz))
    peak_power = psd[peak_idx]

    # 3dB down threshold (half power)
    threshold = peak_power / 2.0

    # Find bins above threshold
    above_threshold = psd >= threshold
    
    # Find left and right edges
    left_edge = None
    right_edge = None

    for i in range(peak_idx, 0, -1):
        if not above_threshold[i]:
            left_edge = freqs[i]
            break
    
    for i in range(peak_idx, len(freqs)):
        if not above_threshold[i]:
            right_edge = freqs[i]
            break
    
    if left_edge is None or right_edge is None:
        return 0.0  # Could not find edges
    
    bandwidth_3db_hz = right_edge - left_edge

    return bandwidth_3db_hz

def measure_adjacent_rejection(freqs: np.ndarray, psd: np.ndarray, peak_freq_hz: float,
                               channel_spacing_hz: float = 200e3) -> float:
    """ 
    Measure adjacent channel rejection

    Compares power at ±200 kHz (US FM channel spacing) to carrier power.
    Good rejection: ≥15 dB.

    Args:
        freqs: Frequency bins in Hz
        psd: Power spectral density (linear scale)
        peak_freq_hz: Carrier peak frequency in Hz
        channel_spacing_hz: Channel spacing in Hz (default: 200 kHz for US FM)

    Returns
        rejection_db: Adjacent channel rejection in dB (average of left/right)
    """
    # Carrier power (integrate ±50 kHz)
    carrier_mask = np.abs(freqs - peak_freq_hz) <= 50e3
    carrier_power = np.sum(psd[carrier_mask])

    # Left adjacent channel power (±50 kHz around -200 kHz offset)
    left_center = peak_freq_hz - channel_spacing_hz
    left_mask = np.abs(freqs - left_center) <= 50e3
    left_power = np.sum(psd[left_mask])

    # Right adjacent channel power (±50 kHz around +200 kHz offset)
    right_center = peak_freq_hz - channel_spacing_hz
    right_mask = np.abs(freqs - right_center) <= 50e3
    right_power = np.sum(psd[right_mask])

    # Average rejection
    avg_adj_power = (left_power + right_power) / 2.0

    if avg_adj_power <= 0:
        return 100.0    # Perfection rejection
    
    rejection_db = 10 * np.log10(carrier_power / avg_adj_power)

    return rejection_db

def measure_rolloff(freqs: np.ndarray, psd: np.ndarray, peak_freq_hz: float) -> dict:
    """ 
    Measure spectral rolloff on left and right sides of carrier

    Detects if signal is bleeding into adjacent channels (asymmetry > 2.0x).

    Args:
        freqs: Frequency bins in Hz
        psd: Power spectral density (linear scale)
        peak_freq_hz: Carrier peak frequency in Hz

    Returns:
        dict with keys:
            - left_slope: dB/kHz on left side
            - right_slope: dB/kHz on right side
            - asymmetry: ratio of slopes (should be ~1.0 for symmetric)
    """
    # Find peak
    peak_idx = np.argmin(np.abs(freqs - peak_freq_hz))
    peak_power_db = 10 * np.log10(psd[peak_idx] + 1e-12)

    # Measure rolloff from +100 kHz to +150 kHz (right side)
    right_start = peak_freq_hz + 100e3
    right_end = peak_freq_hz + 150e3
    right_mask = (freqs >= right_start) & (freqs <= right_end)

    if np.sum(right_mask) > 0:
        right_power_db = 10 * np.log10(np.mean(psd[right_mask]) + 1e-12)
        right_slope = (peak_power_db - right_power_db) / 100.0 # dB per 100 kHz
    else:
        right_slope = 0.0

    # Measure rolloff from -100 kHz to -150 kHz (left side)
    left_start = peak_freq_hz - 150e3
    left_end = peak_freq_hz - 100e3
    left_mask = (freqs >= left_start) & (freqs <= left_end)

    if np.sum(left_mask) > 0:
        left_power_db = 10 * np.log10(np.mean(psd[left_mask]) + 1e-12)
        left_slope = (peak_power_db - left_power_db) / 100.0 # dB per 100 kHz
    else:
        left_slope = 0.0

    # Asymmetry (should be close to 1.0 for symmetric rolloff)
    if left_slope > 0 and right_slope > 0:
        asymmetry = max(left_slope, right_slope) / min(left_slope, right_slope)
    else:
        asymmetry = 999.0 # Invalid

    return {
        'left_slope': left_slope,
        'right_slope': right_slope,
        'asymmetry': asymmetry
    }

def extract_fingerprint(iq_data: np.ndarray, sample_rate: float, center_freq: float) -> dict:
    """ 
    Extract complete FM fingerprint from IQ data

    Args:
        iq_data: Complex IQ samples
        sample_rate: Sample rate in Hz
        center_freq: Center frequency in Hz (tuner setting)

    Returns:
        dict containing all features:
            - peak_freq_hz: Interpolated carrier peak frequency
            - freq_error_hz: Difference from tuner center frequency
            - cnr_db: Carrier-to-noise ratio
            - bandwidth_3db_hz: 3dB bandwidth
            - adjacent_rejection_db: Adjacent channel rejection
            - rolloff_left_slope: Left side rolloff (dB/100kHz)
            - rolloff_right_slope: Right side rolloff (dB/100kHz)
            - rolloff_asymmetry: Ratio of rolloff slopes
            - processing_time_sec: Time to compute features
    """
    t0 = time.time()

    # Compute Welch PSD
    nperseg = 4096      # 586 Hz/bin at 2.4 Mhz
    noverlap = 20489    # 50% overlap
    freqs, psd = signal.welch(
        iq_data,
        fs=sample_rate,
        window='hann',
        nperseg=nperseg,
        noverlap=noverlap,
        return_onesided=False,
        scaling='density'
    )

    # Shift frequencies to be relative to center_freq
    # (Welch returns -fs/2 to +fs/2, we want actual Hz)
    freqs = np.fft.fftshift(freqs)
    psd = np.fft.fftshift(psd)

    # 1. Parabolic peak interpolation
    peak_freq_offset = parabolic_peak_interp(freqs, psd)
    peak_freq_hz = center_freq + peak_freq_offset
    freq_error_hz = peak_freq_offset

    # 2. CNR estimation (MPA)
    cnr_db = estimate_cnr_db(freqs, psd, peak_freq_offset)

    # 3. 3dB bandwidth
    bandwidth_3db_hz = measure_bandwidth_3db(freqs, psd, peak_freq_offset)

    # 4. Adjacent channel rejection
    adjacent_rejection_db = measure_adjacent_rejection(freqs, psd, peak_freq_offset)

    # 5. Spectral rolloff
    rolloff = measure_rolloff(freqs, psd, peak_freq_offset)

    processing_time = time.time() - t0

    return {
        'peak_freq_hz': peak_freq_hz,
        'freq_error_hz': freq_error_hz,
        'cnr_db': cnr_db,
        'bandwidth_3b_hz': bandwidth_3db_hz,
        'adjacent_rejection_db': adjacent_rejection_db,
        'rolloff_left_slope': rolloff['left_slope'],
        'rolloff_right_slope': rolloff['right_slope'],
        'rolloff_asymmetry': rolloff['asymmetry'],
        'processing_time_sec': processing_time
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract FM fingerprint from SigMF capture")
    parser.add_argument("sigmf_path", type=Path, help="Path to .sigmf-meta or .sigmf-data file")

    args = parser.parse_args()

    # Load data
    print(f"Loading {args.sigmf_path}...")
    iq_data, metadata = load_sigmf(args.sigmf_path)

    print(f"Loading {len(iq_data):,} samples")
    print(f"Sample rate: {metadata['sample_rate']/1e6:.1f} MHz")
    print(f"Center freq: {metadata['center_freq']/1e6:.1f} MHz")

    # Extract fingerprint
    print("\nExtracting fingerprint...")
    features = extract_fingerprint(iq_data, metadata['sample_rate'], metadata['center_freq'])

    # Display results
    print("\n== Tier 1 FM Fingerprint ===")
    print(f"Peak frequency:        {features['peak_freq_hz']/1e6:.6f} MHz")
    print(f"Frequency error:       {features['freq_error_hz']/1e3:+.1f} kHz")
    print(f"CNR:                   {features['cnr_db']:.1f} dB")
    print(f"3dB bandwidth:         {features['bandwidth_3db_hz']/1e3:.1f} kHz")
    print(f"Adjacent rejection:    {features['adjacent_rejection_db']:.1f} dB")
    print(f"Rolloff (L/R):         {features['rolloff_left_slope']:.1f} / {features['rolloff_right_slope']:.1f} db/100kHz")
    print(f"Rolloff asymmetry:     {features['rolloff_asymmetry']:.2f}x")
    print(f"Processing time:       {features['processing_time_sec']*1000:.1f} ms")
