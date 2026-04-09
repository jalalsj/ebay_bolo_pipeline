"""
pytest configuration for scripts/tests/.

Adds scripts/ to sys.path so test files can import calculator, config, etc.
directly without package install or relative import gymnastics.
"""

import sys
from pathlib import Path

# scripts/ directory (parent of this tests/ directory)
sys.path.insert(0, str(Path(__file__).parent.parent))
