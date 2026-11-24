"""INPUT_DIR 内の Word / Excel / PowerPoint / PDF / テキストファイルを Markdown に変換し、MARKDOWN_DIR に保存する。

使い方:
    uv run python src/convert_to_markdown.py
"""

import logging
import sys
from pathlib import Path

from markitdown import MarkItDown

# プロジェクトのルートフォルダ（このファイルの 1 つ上の階層）
BASE_DIR = Path(__file__).resolve().parent.parent
# 変換するファイルが入っているフォルダ
INPUT_DIR = BASE_DIR / "data"
# Markdown ファイルの保存先フォルダ
MARKDOWN_DIR = BASE_DIR / "markdown"

SUPPORTED_EXTENSIONS = {".docx", ".xlsx", ".pptx", ".pdf", ".txt"}

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def convert_folder(input_dir: Path, output_dir: Path) -> None:
    """input_dir 直下の対応ファイルを Markdown に変換し、output_dir に保存する。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    markitdown = MarkItDown()

    for path in sorted(input_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:
            markdown = markitdown.convert(path).markdown
        except Exception:
            logger.exception("変換失敗: %s", path.name)
            continue

        # 資料.docx と 資料.pdf のような同名ファイルが上書きし合わないよう、元の拡張子をファイル名に残す（例: 資料_docx.md）
        output_path = output_dir / f"{path.stem}_{path.suffix.lstrip('.')}.md"
        output_path.write_text(markdown, encoding="utf-8")
        logger.info("変換成功: %s -> %s", path.name, output_path)


def main() -> None:
    if not INPUT_DIR.is_dir():
        sys.exit(f"フォルダが見つかりません: {INPUT_DIR}")

    convert_folder(INPUT_DIR, MARKDOWN_DIR)


if __name__ == "__main__":
    main()
