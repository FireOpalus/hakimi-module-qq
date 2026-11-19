"""Compatibility import for the shared Owner delivery queue."""

import sys

from hakimi import proactive_dm as implementation

sys.modules[__name__] = implementation
