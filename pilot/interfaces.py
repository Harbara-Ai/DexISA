"""Compatibility entry point; implementation lives in evaluation.runners.episode."""
import sys
from evaluation.runners import episode as _implementation
sys.modules[__name__] = _implementation
