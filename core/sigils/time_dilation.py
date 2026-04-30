"""
Sigil of Time Dilation (⧖)

Grants the power to accelerate or slow the flow of operations, allowing CodeMage to perform rituals or analyses at superhuman speed or with infinite patience.

Usage: Import and use TimeDilation.dilate(fn, factor)
"""

import time
from typing import Callable, Any

class TimeDilation:
    """
    The TimeDilation sigil manipulates the perceived speed of function execution.
    """
    @staticmethod
    def dilate(fn: Callable[[], Any], factor: float = 1.0) -> Any:
        """
        If factor < 1, slows down execution (waits after call). If > 1, repeats fn for speedup simulation.
        """
        if factor < 1.0:
            result = fn()
            time.sleep((1.0 - factor) * 2)
            return result
        elif factor > 1.0:
            results = [fn() for _ in range(int(factor))]
            return results[-1] if results else None
        else:
            return fn()
