from __future__ import annotations


class CodebaseArchitectError(Exception):
    """Base class for expected Codebase Architect failures."""

    exit_code = 2


class ConfigurationError(CodebaseArchitectError):
    """Configuration is missing, malformed, unsafe, or unsupported."""


class RepositoryError(CodebaseArchitectError):
    """The target repository cannot be safely scanned or analyzed."""


class AnalyzerError(CodebaseArchitectError):
    """A deterministic analyzer failed unexpectedly."""


class ProviderError(CodebaseArchitectError):
    """Base class for model-provider failures."""


class ProviderUnavailableError(ProviderError):
    """The configured provider cannot be reached or used right now."""


class ProviderProtocolError(ProviderError):
    """The provider returned an invalid or unsupported response."""


class SecurityPolicyError(CodebaseArchitectError):
    """A configured operation was blocked by a security policy."""


class ValidationError(CodebaseArchitectError):
    """Generated graph, AIR, or output failed validation."""


class RendererError(CodebaseArchitectError):
    """A diagram renderer failed."""
