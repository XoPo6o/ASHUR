#!/usr/bin/env python3
"""Silly Development entry point for the ASHUR paper-trading daemon."""
import runpy
from pathlib import Path

daemon = Path(__file__).resolve().parent / "trading-lab" / "ashur_daemon.py"
runpy.run_path(str(daemon), run_name="__main__")
