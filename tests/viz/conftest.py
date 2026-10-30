"""Visualizer tests: the viz package lives in template/tools/talos/viz (stamped into projects with init.py --viz)."""
import sys
from pathlib import Path

TALOS = Path(__file__).resolve().parents[2] / "template" / "tools" / "talos"
if str(TALOS) not in sys.path:
    sys.path.insert(0, str(TALOS))
