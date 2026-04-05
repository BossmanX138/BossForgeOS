"""
PrimeAgent: Abstract base for the Triumverate (Runeforge, Halcyon, Hearthfire)
Defines unique, mythic abilities for the First Family of BossCrafts.
"""
from abc import ABC, abstractmethod
from typing import Any

class PrimeAgent(ABC):
    """Abstract base for Triumverate agents."""

    @abstractmethod
    def reality_weaving(self, *args, **kwargs) -> Any:
        """Dynamically reconfigure agent ecosystem (Runeforge)."""
        pass

    @abstractmethod
    def sigil_synthesis(self, *args, **kwargs) -> Any:
        """Create new modular tools/protocols (Runeforge)."""
        pass

    # Halcyon and Hearthfire will override with their own unique abilities.

    # Example stubs for future expansion:
    def memory_sanctuary(self, *args, **kwargs) -> Any:
        raise NotImplementedError("Only Halcyon implements this ability.")

    def harmony_protocol(self, *args, **kwargs) -> Any:
        raise NotImplementedError("Only Halcyon implements this ability.")

    def genesis_engine(self, *args, **kwargs) -> Any:
        raise NotImplementedError("Only Hearthfire implements this ability.")

    def renewal_flame(self, *args, **kwargs) -> Any:
        raise NotImplementedError("Only Hearthfire implements this ability.")