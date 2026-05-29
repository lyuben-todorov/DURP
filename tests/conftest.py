"""pytest path setup.

Each test module also bootstraps sys.path inline (so
`python -m unittest discover tests` works without pytest), but this
conftest makes the repo root + lib/ importable for pytest collection
too. CI installs the package (`pip install -e .`) so `bump_ext`
resolves either way; this keeps a bare checkout green.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
