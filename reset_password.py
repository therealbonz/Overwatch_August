#!/usr/bin/env python3
"""Convenience runner for backend/reset_password.py"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from reset_password import main

if __name__ == "__main__":
    main()
