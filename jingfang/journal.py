"""Store each reading and its resume state in one Markdown file."""

import json
import os
import re
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from tempfile import gettempdir

from .save_reading_log import save_markdown

STATE_HEADER = "\n<!-- jingfang-state:v1\n"
STATE_END = "\n-->\n"


class Journal:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()

    @staticmethod
    def _check_id(run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise ValueError("解卦编号应为 32 位小写十六进制字符")

    def load(self, run_id):
        self._check_id(run_id)
        matches = list(self.directory.glob(f"*_{run_id}.md"))
        if len(matches) != 1:
            raise ValueError(f"找不到唯一的解卦记录 {run_id}")
        path = matches[0]
        _, marker, state = path.read_text(encoding="utf-8").rpartition(STATE_HEADER)
        if not marker and (self.directory / "blackboard.sqlite3").is_file():
            raise ValueError(f"这是历史归档，可直接查看 {path}")
        if not marker or not state.endswith(STATE_END):
            raise ValueError("Markdown 的续跑状态缺失或格式无效")
        run = json.loads(state.removesuffix(STATE_END))
        if not isinstance(run, dict) or run.get("id") != run_id:
            raise ValueError("Markdown 内的解卦编号与文件名不一致")
        return path, run

    @staticmethod
    def save(path, run, markdown):
        state = json.dumps(run, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        state = state.replace("--", "\\u002d\\u002d").replace("<", "\\u003c")
        return save_markdown(markdown + STATE_HEADER + state + STATE_END, path)

    @contextmanager
    def writer(self, run_id):
        self._check_id(run_id)
        key = sha256(os.path.normcase(str(self.directory / run_id)).encode("utf-8")).hexdigest()
        path = Path(gettempdir()) / f"jingfang-v5-{key}.lock"
        with path.open("a+b") as lock:
            lock.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise ValueError("同一卦的记录正在更新，请重试本步") from error
            yield
