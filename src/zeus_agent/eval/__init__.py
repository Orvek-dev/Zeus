from __future__ import annotations

from .wave3 import run_wave3_eval
from .wave4 import run_wave4_eval
from .wave5 import run_wave5_eval
from .wave6 import run_wave6_eval
from .wave7 import run_wave7_eval
from .wave8 import run_wave8_eval
from .final_architecture import run_final_architecture_eval

__all__ = [
    "run_final_architecture_eval",
    "run_wave3_eval",
    "run_wave4_eval",
    "run_wave5_eval",
    "run_wave6_eval",
    "run_wave7_eval",
    "run_wave8_eval",
]
