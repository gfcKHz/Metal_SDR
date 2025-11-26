#!/usr/bin/env python3
"""Tests for BladeRF backend (skeleton)"""

import unittest

import numpy as np

from scripts.capture.backends.bladerf import BladeRFBackend


class TestBladeRFBackend(unittest.TestCase):
    def setUp(self):
        try:
            self.backend = BladeRFBackend()
        except (ImportError, RuntimeError) as exc:
            self.skipTest(f"bladeRF unavailable: {exc}")

    def test_capture(self):
        try:
            iq = self.backend.capture(1.8e9, 20e6, 0.05, 30)
        except RuntimeError as exc:
            self.skipTest(f"bladeRF capture failed (likely no hardware): {exc}")

        self.assertIsInstance(iq, np.ndarray)
        self.assertEqual(iq.dtype, np.complex64)
        self.assertGreater(len(iq), 0)


if __name__ == "__main__":
