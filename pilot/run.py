"""Compatibility entry point; implementation lives in evaluation.runners.pilot."""
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sys
from evaluation.runners import pilot as _implementation
if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
