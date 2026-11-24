"""Save a finished Jingfang reading record in the project's reading-logs folder."""

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4


def save_markdown(record, destination):
    """Write a complete record atomically, including on archive retries."""
    if not record.strip():
        raise ValueError("the reading record is empty")
    if not record.endswith("\n"):
        record += "\n"

    destination.parent.mkdir(parents=True, exist_ok=True)
    draft = NamedTemporaryFile(dir=destination.parent, encoding="utf-8", mode="w", newline="\n", delete=False)
    draft_path = Path(draft.name)
    try:
        with draft:
            draft.write(record)
        draft_path.replace(destination)
    finally:
        draft_path.unlink(missing_ok=True)

    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, help="UTF-8 Markdown file for one reading")
    args = parser.parse_args()

    record = args.record.read_text(encoding="utf-8-sig")
    log_dir = Path(__file__).resolve().parents[1] / "reading-logs"
    recorded_at = datetime.now(timezone(timedelta(hours=8)))
    timestamp = recorded_at.strftime("%Y-%m-%d_%H-%M-%S")
    destination = log_dir / f"{timestamp}_{uuid4().hex}.md"
    try:
        print(save_markdown(record, destination))
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
