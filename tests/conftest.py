from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
root_path = str(ROOT_DIR)
if root_path not in sys.path:
    sys.path.insert(0, root_path)
