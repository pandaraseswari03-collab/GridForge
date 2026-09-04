"""Explicit UI-Core configuration for line creation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LineCreationParameters:
    """Engineering inputs supplied by the UI configuration boundary."""

    r: float
    x: float
    b: float = 0.0
    name: str = ""
    rate_mva: float = 100.0

    def __post_init__(self) -> None:
        for field_name in ("r", "x", "b", "rate_mva"):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)):
                raise TypeError(f"{field_name} must be numeric")
        if not isinstance(self.name, str):
            raise TypeError("name must be a string")


__all__ = ["LineCreationParameters"]
