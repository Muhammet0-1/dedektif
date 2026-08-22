"""Project-specific exceptions."""


class DedektifError(Exception):
    """Base exception for expected application failures."""


class ConfigurationError(DedektifError):
    """Raised when user-supplied configuration is invalid."""


class TransportError(DedektifError):
    """Raised when a bounded HTTP observation cannot be completed."""
