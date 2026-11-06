"""Rebuild the four T19-owned semantic stainless EAF/AOD assets, not T26's remaining 26."""
from pathlib import Path
import runpy
import sys

core=Path(__file__).resolve().parent.parent/'steelmaking/build.py'
sys.path.insert(0,str(core.parent))
runpy.run_path(str(core),run_name='stainless_builder')['main']('stainless')
