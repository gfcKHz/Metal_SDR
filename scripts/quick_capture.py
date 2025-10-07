#!/usr/bin/env python3
import sys 
from capture_rtl_real import capture_rtl_sdr

freq = float(sys.argv[1]) if len(sys.argv) > 1 else 105.9
rate = float(sys.argv[2]) if len(sys.argv) > 2 else 1.2
dur = int(sys.argv[3]) if len(sys.argv) > 3 else 3 

capture_rtl_sdr(duration=dur, center_freq=freq*1e6, sample_rate=rate*1e6)
