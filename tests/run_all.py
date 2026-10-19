"""Run every tests/test_*.py suite. Exit code is non-zero on any failure, error or skip.

Skips count as failures: a CI runner missing bash or jq would otherwise go green
without testing anything.

Run: python3 tests/run_all.py
"""

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(TESTS), top_level_dir=str(TESTS))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.skipped:
        print(f"\nFAILED: {len(result.skipped)} test(s) skipped, install the missing tools (bash, jq).", file=sys.stderr)
    sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
