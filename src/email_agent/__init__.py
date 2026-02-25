__all__ = ["EmailAgent"]


def __getattr__(name: str):
    if name == "EmailAgent":
        from .service import EmailAgent

        return EmailAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
