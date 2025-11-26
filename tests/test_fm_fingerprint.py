#!/usr/bin/env python3
"""
Regression tests for FM fingerprinting

Tests validation requirements from blog post:
- CNR extraction accuracy within 2 dB tolerance
- Frequency precision within 100 Hz
- Dimensional consistency of power measurements
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest
from scipy import signal

from scripts.fingerprinting.fm_fingerprint import (
    estimate_cnr_db,
    parabolic_peak_interp,
    measure_adjacent_rejection,
    measure_bandwidth_3db,
    psd_to_power,
    extract_fingerprint,
)


@pytest.fixture(autouse=True)
def _seed_numpy_rng():
    """Ensure deterministic noise generation for reproducible tests."""
    np.random.seed(0)


class TestSyntheticSignals:
    """Test fingerprint extraction on synthetic IQ data with known properties"""

    def generate_tone(self, freq_hz: float, sample_rate: float, duration: float,
                      snr_db: float = None) -> np.ndarray:
        """
        Generate synthetic complex tone with optional AWGN

        Args:
            freq_hz: Tone frequency offset from DC (Hz)
            sample_rate: Sample rate (Hz)
            duration: Signal duration (seconds)
            snr_db: Signal-to-noise ratio in dB (None = no noise)

        Returns:
            Complex IQ samples
        """
        n_samples = int(duration * sample_rate)
        t = np.arange(n_samples) / sample_rate

        # Generate complex tone
        signal_iq = np.exp(2j * np.pi * freq_hz * t)

        if snr_db is not None:
            # Add complex AWGN
            signal_power = np.mean(np.abs(signal_iq) ** 2)
            noise_power = signal_power / (10 ** (snr_db / 10))
            noise = np.sqrt(noise_power / 2) * (
                np.random.randn(n_samples) + 1j * np.random.randn(n_samples)
            )
            signal_iq = signal_iq + noise

        return signal_iq

    def compute_psd(self, iq_data: np.ndarray, sample_rate: float):
        """Compute PSD using same parameters as fingerprinting code"""
        nperseg = 4096
        noverlap = 2048
        freqs, psd = signal.welch(
            iq_data,
            fs=sample_rate,
            window='hann',
            nperseg=nperseg,
            noverlap=noverlap,
            return_onesided=False,
            scaling='density'
        )
        freqs = np.fft.fftshift(freqs)
        psd = np.fft.fftshift(psd)
        return freqs, psd


class TestCNRAccuracy(TestSyntheticSignals):
    """Validate CNR extraction accuracy within 2 dB tolerance"""

    @pytest.mark.parametrize("true_snr_db", [10.0, 20.0, 30.0, 40.0])
    def test_cnr_extraction_accuracy(self, true_snr_db):
        """CNR should match known SNR within 2 dB"""
        sample_rate = 2.4e6
        freq_offset = 0.0  # Carrier at DC
        duration = 0.5  # seconds

        # Generate tone with known SNR
        iq_data = self.generate_tone(freq_offset, sample_rate, duration, true_snr_db)

        # Compute PSD
        freqs, psd = self.compute_psd(iq_data, sample_rate)

        # Estimate CNR
        measured_cnr = estimate_cnr_db(freqs, psd, peak_freq_hz=0.0)

        # Validate within 2 dB tolerance
        error = abs(measured_cnr - true_snr_db)
        assert error < 2.0, (
            f"CNR error {error:.2f} dB exceeds 2 dB tolerance "
            f"(true={true_snr_db:.1f}, measured={measured_cnr:.2f})"
        )

    def test_cnr_dimensional_consistency(self):
        """CNR should be independent of FFT length (dimensional consistency)"""
        sample_rate = 2.4e6
        freq_offset = 0.0
        duration = 0.5
        true_snr = 25.0

        iq_data = self.generate_tone(freq_offset, sample_rate, duration, true_snr)

        # Test with different FFT lengths
        cnr_results = []
        for nperseg in [2048, 4096, 8192]:
            noverlap = nperseg // 2
            freqs, psd = signal.welch(
                iq_data,
                fs=sample_rate,
                window='hann',
                nperseg=nperseg,
                noverlap=noverlap,
                return_onesided=False,
                scaling='density'
            )
            freqs = np.fft.fftshift(freqs)
            psd = np.fft.fftshift(psd)

            cnr = estimate_cnr_db(freqs, psd, peak_freq_hz=0.0)
            cnr_results.append(cnr)

        # All CNR measurements should be within 1 dB of each other
        cnr_std = np.std(cnr_results)
        assert cnr_std < 1.0, (
            f"CNR varies by {cnr_std:.2f} dB across FFT lengths "
            f"(should be <1 dB): {cnr_results}"
        )


class TestFrequencyAccuracy(TestSyntheticSignals):
    """Validate frequency precision within 100 Hz"""

    @pytest.mark.parametrize("freq_offset_hz", [-50e3, -10e3, 0.0, 10e3, 50e3])
    def test_peak_interpolation_accuracy(self, freq_offset_hz):
        """Peak frequency should be accurate within 100 Hz"""
        sample_rate = 2.4e6
        duration = 0.5
        snr_db = 30.0  # High SNR for good accuracy

        # Generate tone at known frequency offset
        iq_data = self.generate_tone(freq_offset_hz, sample_rate, duration, snr_db)

        # Compute PSD
        freqs, psd = self.compute_psd(iq_data, sample_rate)

        # Estimate peak frequency
        measured_offset = parabolic_peak_interp(freqs, psd)

        # Validate within 100 Hz tolerance
        error = abs(measured_offset - freq_offset_hz)
        assert error < 100.0, (
            f"Frequency error {error:.1f} Hz exceeds 100 Hz tolerance "
            f"(true={freq_offset_hz:.0f}, measured={measured_offset:.1f})"
        )


class TestAdjacentChannelRejection(TestSyntheticSignals):
    """Validate adjacent-channel rejection calculation"""

    def test_adjacent_rejection_left_right_symmetry(self):
        """Adjacent rejection should handle left/right channels correctly"""
        sample_rate = 2.4e6
        duration = 0.5

        # Generate carrier at 0 Hz
        carrier = self.generate_tone(0.0, sample_rate, duration, snr_db=40.0)

        # Add weak adjacent channels at ±200 kHz
        left_adj = 0.1 * self.generate_tone(-200e3, sample_rate, duration, snr_db=None)
        right_adj = 0.1 * self.generate_tone(200e3, sample_rate, duration, snr_db=None)

        iq_data = carrier + left_adj + right_adj

        # Compute PSD
        freqs, psd = self.compute_psd(iq_data, sample_rate)

        # Measure rejection
        rejection = measure_adjacent_rejection(freqs, psd, peak_freq_hz=0.0)

        # Should have significant rejection (>15 dB as per spec)
        assert rejection > 15.0, f"Adjacent rejection {rejection:.1f} dB < 15 dB threshold"

    def test_adjacent_rejection_uses_mean_not_sum(self):
        """
        Regression test: adjacent rejection should use mean power density
        (not sum vs mean mismatch)
        """
        sample_rate = 2.4e6
        duration = 0.5

        # Single carrier, no adjacent channels
        iq_data = self.generate_tone(0.0, sample_rate, duration, snr_db=30.0)

        # Test with different FFT lengths
        rejection_results = []
        for nperseg in [2048, 4096, 8192]:
            noverlap = nperseg // 2
            freqs, psd = signal.welch(
                iq_data,
                fs=sample_rate,
                window='hann',
                nperseg=nperseg,
                noverlap=noverlap,
                return_onesided=False,
                scaling='density'
            )
            freqs = np.fft.fftshift(freqs)
            psd = np.fft.fftshift(psd)

            rejection = measure_adjacent_rejection(freqs, psd, peak_freq_hz=0.0)
            rejection_results.append(rejection)

        # Rejection should be consistent across FFT lengths
        rejection_std = np.std(rejection_results)
        assert rejection_std < 2.0, (
            f"Rejection varies by {rejection_std:.2f} dB across FFT lengths "
            f"(dimensional mismatch?): {rejection_results}"
        )


class TestPSDBinWidthScaling:
    """Validate proper PSD bin-width scaling"""

    def test_psd_to_power_conversion(self):
        """Test that PSD to power conversion uses correct bin-width scaling"""
        # Create synthetic PSD (constant power spectral density)
        n_bins = 1000
        psd_value = 1e-6  # W/Hz
        psd = np.full(n_bins, psd_value)

        # Frequency resolution
        freq_resolution = 586.0  # Hz (typical for 2.4 MHz / 4096)

        # Convert to total power
        total_power = psd_to_power(psd, freq_resolution)

        # Expected: sum(psd) * freq_resolution
        expected_power = n_bins * psd_value * freq_resolution

        assert np.isclose(total_power, expected_power), (
            f"PSD to power conversion incorrect: "
            f"expected={expected_power:.2e}, got={total_power:.2e}"
        )


class TestBandwidthMeasurement(TestSyntheticSignals):
    """Validate 3dB bandwidth measurement"""

    def test_bandwidth_measurement_consistency(self):
        """Bandwidth measurement should be consistent across multiple runs"""
        sample_rate = 2.4e6
        duration = 0.5

        # Generate FM-like signal (tone with some bandwidth)
        iq_data = self.generate_tone(0.0, sample_rate, duration, snr_db=30.0)

        # Measure bandwidth multiple times
        bandwidth_results = []
        for _ in range(5):
            freqs, psd = self.compute_psd(iq_data, sample_rate)
            bw = measure_bandwidth_3db(freqs, psd, peak_freq_hz=0.0)
            bandwidth_results.append(bw)

        # Results should be identical (deterministic)
        assert len(set(bandwidth_results)) == 1, (
            f"Bandwidth measurement non-deterministic: {bandwidth_results}"
        )


class TestExtractFingerprint(TestSyntheticSignals):
    """Regression tests for top-level feature extraction."""

    def test_extract_returns_bandwidth_key(self):
        """Ensure bandwidth is reported with the documented key."""
        sample_rate = 2.4e6
        duration = 0.2
        center_freq = 100e6

        iq_data = self.generate_tone(0.0, sample_rate, duration, snr_db=30.0)
        features = extract_fingerprint(iq_data, sample_rate, center_freq)

        assert 'bandwidth_3db_hz' in features, "bandwidth key missing from features dict"
        assert features['bandwidth_3db_hz'] >= 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
