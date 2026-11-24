"""Compatibility entry point for the Markdown journal checks."""

from pathlib import Path
from runpy import run_path


if __name__ == "__main__":
    run_path(str(Path(__file__).with_name("journal_check.py")), run_name="__main__")
