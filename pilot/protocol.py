"""Compatibility entry point; implementation lives in evaluation.agents.protocol."""
import sys
from evaluation.agents import protocol as _implementation
sys.modules[__name__] = _implementation
