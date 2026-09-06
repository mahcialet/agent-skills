"""Typed errors whose messages are safe to show after redaction."""

from __future__ import annotations


class TicketStateError(Exception):
    """Base class for expected failures."""

    code = "TICKET_STATE_ERROR"


class ConfigurationError(TicketStateError):
    code = "CONFIGURATION_ERROR"


class IdentityError(TicketStateError):
    code = "IDENTITY_ERROR"


class PermissionDenied(TicketStateError):
    code = "PERMISSION_DENIED"


class UnsafeContentError(TicketStateError):
    code = "NEEDS_REVIEW"


class StorageError(TicketStateError):
    code = "STORAGE_ERROR"


class StateError(TicketStateError):
    code = "STATE_ERROR"


class RemoteError(TicketStateError):
    code = "REMOTE_ERROR"

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retryable: bool = False,
        result_unknown: bool = False,
        mutation_attempted: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.result_unknown = result_unknown
        self.mutation_attempted = mutation_attempted
