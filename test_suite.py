#!/usr/bin/env python3
"""
Compatibility runner.

The test suite is implemented as standard pytest tests in tests/. This script
simply invokes pytest on that directory so `python test_suite.py` and
`python -m pytest -q` run the same tests. Exit code is pytest's exit code.
"""
import sys
from pathlib import Path

import pytest

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    sys.exit(pytest.main(['-q', str(root / 'tests')]))
