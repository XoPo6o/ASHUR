#!/usr/bin/env python3
"""Silly Development entry point for the ASHUR paper-trading daemon."""
import os
import runpy
from pathlib import Path

os.environ.setdefault("ASHUR_RESET_PAPER_BASELINE_ID", "ashur-paper-30d-2026-11-25-v2")
supervisor = Path(__file__).resolve().parent / "trading-lab" / "ashur_supervisor.py"
runpy.run_path(str(supervisor), run_name="__main__")
