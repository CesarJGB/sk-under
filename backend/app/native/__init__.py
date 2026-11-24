"""Autenticación nativa de ChillyRoom y sesiones web aisladas (Fase 6.8)."""

from .client import NativeAuthClient
from .errors import NativeError
from .distributions import DISTRIBUTIONS, Distribution, get_distribution
from .store import NativeStore

__all__ = [
    "DISTRIBUTIONS",
    "Distribution",
    "NativeAuthClient",
    "NativeError",
    "NativeStore",
    "get_distribution",
]
