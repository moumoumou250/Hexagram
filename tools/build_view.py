"""Refresh the single-case preview in the default HTML template."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jingfang.view import render_page

EXAMPLE = {
    "id": "18", "mask": 4,
    "question": "谒贵，能否见到所求见的贵人？", "role": "官鬼", "month": "酉", "day": "丙寅",
    "primary": {"source": "base", "position": 3, "branch": "酉", "element": "金"},
    "label": "《增删卜易》书例 · 谒贵", "candidates": [], "pending": [], "notes": [],
    "summary": "书例断待子日方能得见。三爻官鬼酉金持世，临酉月；动化午火回头克。子日冲去午火，书载丙子日得见。",
    "source": "书例依据《增删卜易·月将章》，见项目 CASES.md 第 9 例。变爻六亲按本卦宫五行。",
}

if __name__ == "__main__":
    page = ROOT / "templates" / "hexagram-view.html"
    page.write_text(render_page(EXAMPLE, (ROOT / "gua.sql").read_text(encoding="utf-8-sig")), encoding="utf-8")
