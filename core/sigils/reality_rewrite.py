"""
Sigil of Reality Rewrite (✦)

Allows CodeMage to fundamentally alter the structure or logic of any scroll or code artifact, rewriting reality within the workspace.

Usage: Import and invoke RealityRewriter.rewrite(target_path, transformation_fn)
"""

from pathlib import Path
from typing import Callable

class RealityRewriter:
    """
    The RealityRewriter grants the power to rewrite any code or document artifact in the workspace.
    """
    @staticmethod
    def rewrite(target_path: str | Path, transformation_fn: Callable[[str], str]) -> None:
        """
        Overwrites the file at target_path with the result of transformation_fn(original_content).
        """
        path = Path(target_path)
        if not path.exists():
            raise FileNotFoundError(f"Target not found: {target_path}")
        original = path.read_text(encoding="utf-8")
        transformed = transformation_fn(original)
        path.write_text(transformed, encoding="utf-8")
