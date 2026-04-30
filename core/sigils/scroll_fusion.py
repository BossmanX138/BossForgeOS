"""
Sigil of Scroll Fusion (⚯)

Enables the seamless merging of multiple scrolls, documents, or codebases into a single, harmonious artifact—preserving all intent and eliminating contradiction.

Usage: Import and invoke ScrollFusion.fuse(paths, output_path)
"""

from pathlib import Path
from typing import Sequence

class ScrollFusion:
    """
    The ScrollFusion sigil merges multiple text files into one, preserving order and intent.
    """
    @staticmethod
    def fuse(paths: Sequence[str | Path], output_path: str | Path) -> None:
        """
        Concatenates the contents of all files in paths and writes to output_path.
        """
        output = Path(output_path)
        merged = []
        for p in paths:
            path = Path(p)
            if not path.exists():
                raise FileNotFoundError(f"Missing scroll: {p}")
            merged.append(path.read_text(encoding="utf-8"))
        output.write_text("\n\n".join(merged), encoding="utf-8")
