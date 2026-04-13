"""
Code generation backend registry.

To add a new backend:
  1. Create a new file in this directory (e.g., arduino.py)
  2. Subclass CodegenBackend
  3. Add it to BACKENDS below

That's it.
"""

from __future__ import annotations

from .base import CodegenBackend
from .userspace import UserspaceBackend
from .kernel import KernelBackend

# Registry of available backends, keyed by name
BACKENDS: dict[str, type[CodegenBackend]] = {
    "userspace": UserspaceBackend,
    "kernel": KernelBackend,
}


def get_backend(name: str) -> CodegenBackend:
    """Instantiate a backend by name.

    Args:
        name: One of the keys in BACKENDS (e.g., "userspace", "kernel").

    Returns:
        An instance of the requested backend.

    Raises:
        ValueError: if the backend name is not recognized.
    """
    cls = BACKENDS.get(name)
    if cls is None:
        available = ", ".join(sorted(BACKENDS.keys()))
        raise ValueError(f"Unknown backend '{name}'. Available: {available}")
    return cls()
