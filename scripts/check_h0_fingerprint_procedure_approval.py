#!/usr/bin/env python3
"""Read-only entry point for the H0 fingerprint-procedure approval channel."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from automation.procedure_approval import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
