# ============================================================
# File: core/network/endpoint.py
# GridForge V2 — Network Endpoint Resolution
# Author: Subhendu Mishra
# ============================================================

"""
GridForge V2 Network Endpoint Resolution.

Provides canonical, read-only resolution from a model Terminal to its
electrical Bus.

## Architecture

The model layer owns:

```
Equipment
    |
    +-- Terminal
          |
          +-- endpoint
```

The Network layer interprets that local endpoint relationship:

```
Terminal
    |
    +-- endpoint
          |
          +-- Bus
              or
          +-- endpoint.bus -> Bus
```

This module does not mutate model objects.

It does not:

```
- attach or detach terminals;
- transfer terminal ownership;
- construct topology;
- register equipment;
- assign numerical indices;
- construct Y-bus matrices;
- perform electrical calculations.
```

## Endpoint interpretation

For compatibility with the current model architecture, an attached
endpoint may be represented in either of two forms:

1. Direct Bus-like endpoint

   ```
   terminal.endpoint -> Bus
   ```

2. Endpoint wrapper or adapter

   ```
   terminal.endpoint -> object
                           |
                           +-- .bus -> Bus
   ```

The first form is preferred as the direct model representation.

The second form remains supported where an existing endpoint adapter is
required.

Terminal-to-Terminal chaining is not resolved by this module.

A Terminal is an owned connection point, not an endpoint wrapper and
not a topology traversal mechanism.

Copyright © 2026 Subhendu Mishra
All Rights Reserved.
"""

from __future__ import annotations

from typing import Any

# ============================================================
# TERMINAL -> BUS RESOLUTION
# ============================================================


def resolve_terminal_bus(
    terminal: Any,
) -> Any:
    """
    Resolve a Terminal to its electrical Bus.

    ```
    Resolution order
    ----------------

    1. Read ``terminal.endpoint``.
    2. Reject a missing endpoint.
    3. Reject Terminal-to-Terminal chaining.
    4. If the endpoint exposes a non-None ``bus`` attribute,
       resolve through that attribute.
    5. Otherwise treat the endpoint itself as the resolved Bus-like
       object.

    This function is intentionally read-only.

    Parameters
    ----------
    terminal:
        Terminal-like object exposing an ``endpoint`` attribute.

    Returns
    -------
    Any
        The resolved Bus-like object.

    Raises
    ------
    ValueError
        If the terminal is missing, has no endpoint, or resolves to
        another Terminal.

    Notes
    -----
    Concrete Bus type validation belongs to the appropriate Network
    and validation contracts. This resolver performs only canonical
    endpoint interpretation.
    """

    if terminal is None:
        raise ValueError(
            "Terminal cannot be None."
        )

    endpoint = getattr(
        terminal,
        "endpoint",
        None,
    )

    if endpoint is None:
        raise ValueError(
            "Terminal does not have an endpoint."
        )

    # Import locally to avoid creating a module-level dependency cycle
    # between model and network package initialization.
    from core.model.terminal import Terminal

    if isinstance(
        endpoint,
        Terminal,
    ):
        raise ValueError(
            "Terminal-to-Terminal endpoint chaining is not supported."
        )

    resolved_bus = getattr(
        endpoint,
        "bus",
        None,
    )

    if resolved_bus is not None:
        return resolved_bus

    return endpoint


__all__ = [
    "resolve_terminal_bus",
]
