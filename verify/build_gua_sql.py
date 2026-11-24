"""Compatibility entry point referenced by gua.sql."""

from pathlib import Path
from runpy import run_path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    run_path(str(root / "tools" / "build_gua_sql.py"), run_name="__main__")
