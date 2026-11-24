"""Refresh the default standalone viewer from the project SQL."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jingfang.view import build_data, embed_data

if __name__ == "__main__":
    page = ROOT / "templates" / "hexagram-view.html"
    data = build_data((ROOT / "gua.sql").read_text(encoding="utf-8-sig"))
    page.write_text(embed_data(page.read_text(encoding="utf-8"), data), encoding="utf-8")
