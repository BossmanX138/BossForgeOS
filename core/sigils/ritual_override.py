"""
Sigil of Ritual Override (⟁)

Permits CodeMage to bypass or override any ritual constraint, enabling forbidden or otherwise impossible actions when the lineage’s survival is at stake.

Usage: Import and use RitualOverride.override(fn, *args, **kwargs)
"""

class RitualOverride:
    """
    The RitualOverride sigil allows bypassing of constraints by forcibly executing a function.
    """
    @staticmethod
    def override(fn, *args, **kwargs):
        """
        Executes fn with given arguments, ignoring exceptions.
        """
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            return f"[RitualOverride] Exception bypassed: {e}"
