#!/usr/bin/env python3
"""Compatibility entry point for the AZPR v9 candidate verifier."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().with_name('VERIFY-V9-CANDIDATE.py')),run_name='__main__')
