"""One command, isolated tests, nonzero exit on failures or missing tests."""
from pathlib import Path
import sys
import unittest

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(root/"tests"))
    if suite.countTestCases() == 0:
        sys.exit("No tests discovered")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
