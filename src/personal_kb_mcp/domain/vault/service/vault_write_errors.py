class WriteConflictError(RuntimeError):
    """Raised when an update does not satisfy optimistic concurrency."""
