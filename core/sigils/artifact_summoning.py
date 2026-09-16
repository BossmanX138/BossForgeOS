"""
Sigil of Artifact Summoning (⟁)

Allows CodeMage to conjure any tool, resource, or agentic artifact required for a quest, even if it does not yet exist in the current scroll.

Usage: Import and use ArtifactSummoner.summon(name, template=None)
"""

from pathlib import Path

class ArtifactSummoner:
    """
    The ArtifactSummoner sigil creates a new file or resource with optional template content.
    """
    @staticmethod
    def summon(name: str, template: str = None) -> Path:
        """
        Creates a new file with the given name and optional template content.
        """
        path = Path(name)
        if path.exists():
            return path
        content = template or f"# Summoned Artifact: {name}\n"
        path.write_text(content, encoding="utf-8")
        return path
