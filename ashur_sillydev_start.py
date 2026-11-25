#!/usr/bin/env python3
"""Silly Development entry point for the ASHUR paper-trading daemon."""
import runpy
from pathlib import Path

supervisor = Path(__file__).resolve().parent / "trading-lab" / "ashur_supervisor.py"
runpy.run_path(str(supervisor), run_name="__main__")
