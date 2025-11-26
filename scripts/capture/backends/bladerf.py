#!/usr/bin/env python3
"""BladeRF 2.0 hardware backend"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from ..capture_manager import SDRBackend
@dataclass
class BladeRFStreamConfig:
    """Simple container for stream parameters."""

    num_buffers: int = 16
    buffer_size: int = 8192
    num_transfers: int = 8
    timeout_ms: int = 5000


class BladeRFBackend(SDRBackend):
    """BladeRF 2.0 backend using bladeRF Python API."""

    def __init__(
        self,
        serial: Optional[str] = None,
        channel: int = 0,
        stream: Optional[BladeRFStreamConfig] = None,
    ):
        """
        Initialize BladeRF backend.

        Args:
            serial: Optional device serial to target a specific radio.
            channel: RX channel index (0 or 1 for MIMO boards).
            stream: Streaming config (buffers, sizes, timeout).
        """
        try:
            import bladerf
        except ImportError as exc:
            raise ImportError(
                "bladeRF Python library not installed. Install with `pip install bladerf`."
            ) from exc

        self.bladerf = bladerf
        self.serial = serial
        self.channel_index = channel
        self.stream_cfg = stream or BladeRFStreamConfig()

        # Common constants pulled once for readability.
        self.rx_channel = self.bladerf.CHANNEL_RX(channel)
        self.stream_layout = getattr(
            self.bladerf, "CHANNEL_LAYOUT_RX", self.rx_channel
        )  # Some bindings expect layout instead of channel on sync_config.
        self.sample_format = getattr(
            self.bladerf, "FORMAT_SC16_Q11", None
        )  # Expected for 12-bit IQ.

        self.device = self._open_device()
        serial_info = getattr(self.device, "serial", "unknown")
        print(f"[BladeRF] Connected (serial={serial_info}) on RX{channel}")

    @property
    def name(self) -> str:
        return "bladerf"

    def get_frequency_range(self) -> Tuple[float, float]:
        """BladeRF 2.0 xA9 frequency range."""
        return (47e6, 6e9)  # 47 MHz - 6 GHz

    def get_supported_sample_rates(self) -> list:
        """BladeRF 2.0 supports up to 61.44 Msps."""
        return [
            2.4e6,  # Compatible with RTL-SDR captures
            5e6,
            10e6,
            20e6,
            40e6,
            61.44e6,  # Max sample rate
        ]

    def capture(
        self, center_freq: float, sample_rate: float, duration: float, gain: float
    ) -> np.ndarray:
        """
        Capture IQ using bladeRF sync API.

        Args:
            center_freq: Center frequency (Hz).
            sample_rate: Sample rate (Hz).
            duration: Capture duration (seconds).
            gain: Overall RX gain (dB).

        Returns:
            Complex64 numpy array of IQ samples.

        Raises:
            ValueError: Invalid parameters.
            RuntimeError: Device/configuration errors during capture.
        """
        self._validate_params(center_freq, sample_rate, duration)
        num_samples = int(duration * sample_rate)

        # Configure front-end.
        self._configure_radio(center_freq, sample_rate, gain)
        self._configure_stream()

        # Run capture.
        try:
            self.device.enable_module(self.rx_channel, True)
            raw = self._sync_rx(num_samples)
        finally:
            self.device.enable_module(self.rx_channel, False)

        iq = self._normalize_sc16(raw)
        return iq.astype(np.complex64)

    def _open_device(self):
        try:
            if self.serial:
                return self.bladerf.BladeRF(self.serial)
            return self.bladerf.BladeRF()
        except Exception as exc:  # Broad on purpose to catch binding-specific errors.
            raise RuntimeError(
                "Unable to open bladeRF device. Ensure the radio is connected and "
                "libbladeRF drivers are installed."
            ) from exc

    def _validate_params(self, center_freq: float, sample_rate: float, duration: float):
        min_freq, max_freq = self.get_frequency_range()
        if not (min_freq <= center_freq <= max_freq):
            raise ValueError(
                f"Frequency {center_freq/1e6:.1f} MHz out of range "
                f"for bladeRF: {min_freq/1e6:.1f} - {max_freq/1e6:.1f} MHz"
            )
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
        if duration <= 0:
            raise ValueError("Duration must be positive")

    def _configure_radio(self, center_freq: float, sample_rate: float, gain: float):
        """Apply frequency, rate, bandwidth, and gain."""
        # Sample rate (returns actual).
        try:
            actual_sr = self.device.set_sample_rate(self.rx_channel, int(sample_rate))
        except AttributeError:
            # Older binding signature: set_sample_rate(channel, rate)
            actual_sr = self.device.set_sample_rate(self.rx_channel, sample_rate)
        sr_hz = actual_sr[0] if isinstance(actual_sr, (list, tuple)) else actual_sr
        print(f"[BladeRF] Sample rate set to {sr_hz/1e6:.3f} Msps")

        # Bandwidth: match sample_rate where possible.
        try:
            actual_bw = self.device.set_bandwidth(self.rx_channel, int(sample_rate))
            bw_hz = actual_bw[0] if isinstance(actual_bw, (list, tuple)) else actual_bw
            print(f"[BladeRF] Bandwidth set to {bw_hz/1e6:.3f} MHz")
        except Exception as exc:
            print(f"[BladeRF] Warning: bandwidth set failed ({exc})")

        # Frequency.
        self.device.set_frequency(self.rx_channel, int(center_freq))

        # Gain: keep it simple—single combined gain setting.
        try:
            self.device.set_gain(self.rx_channel, int(gain))
        except Exception as exc:
            # Some bindings expose per-stage gain; surface guidance.
            raise RuntimeError(
                "Failed to set gain. If your binding expects per-stage gain, "
                "configure LNA/VGA manually."
            ) from exc

    def _configure_stream(self):
        """Configure sync stream (SC16 Q11)."""
        if self.sample_format is None:
            raise RuntimeError("bladeRF bindings missing FORMAT_SC16_Q11")
        try:
            self.device.sync_config(
                self.stream_layout,
                self.sample_format,
                self.stream_cfg.num_buffers,
                self.stream_cfg.buffer_size,
                self.stream_cfg.num_transfers,
                self.stream_cfg.timeout_ms,
            )
        except Exception as exc:
            raise RuntimeError("Failed to configure bladeRF sync stream") from exc

    def _sync_rx(self, num_samples: int):
        """Wrapper to handle binding differences for sync_rx."""
        try:
            return self.device.sync_rx(num_samples)
        except TypeError:
            return self.device.sync_rx(num_samples, timeout_ms=self.stream_cfg.timeout_ms)

    def _normalize_sc16(self, raw) -> np.ndarray:
        """
        Convert SC16_Q11 to complex64 in [-1, 1] range.

        The Python binding may return shape (N, 2) or interleaved 1-D.
        """
        arr = np.asarray(raw)
        if arr.ndim == 2 and arr.shape[1] == 2:
            i = arr[:, 0].astype(np.float32)
            q = arr[:, 1].astype(np.float32)
        else:
            flat = arr.reshape(-1)
            i = flat[0::2].astype(np.float32)
            q = flat[1::2].astype(np.float32)
        scale = 2048.0  # SC16_Q11 full-scale for 12-bit data in 16-bit container.
        return (i + 1j * q) / scale