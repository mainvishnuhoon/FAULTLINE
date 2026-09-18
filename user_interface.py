#!/usr/bin/env python3
"""Convenience root launcher for the FAULTLINE User Interface (Red & White Theme)."""

import sys
from pathlib import Path

# Ensure root directory is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from User_Interface.__main__ import main

if __name__ == "__main__":
    main()
